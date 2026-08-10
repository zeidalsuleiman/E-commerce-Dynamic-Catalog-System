# 06 — The Constraint Rules Engine

## The gap this fills

Before this phase the model could express two kinds of constraint:

| Mechanism | Expresses |
|---|---|
| `product_type_attribute.is_required` | This field must be filled |
| `attribute_option_dependency` | Which *options* are valid given a parent option |

Neither can say **"if condition is new, mileage must be 0."** That is a value
constraint on one attribute triggered by another attribute's value —
`attribute_option_dependency` links option to option, and mileage is not an
option attribute.

This was identified as the clearest extension point in the model and built as
Phase 11.

---

## The table

```sql
CREATE TABLE attribute_rule (
  id                   INT UNSIGNED AUTO_INCREMENT,
  product_type_id      INT UNSIGNED NOT NULL,
  trigger_attribute_id INT UNSIGNED NOT NULL,
  trigger_option_id    INT UNSIGNED NOT NULL,
  target_attribute_id  INT UNSIGNED NOT NULL,
  rule_type            ENUM('force_value','hide','require','max','min'),
  rule_value           VARCHAR(64) NULL,
  message              VARCHAR(255) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_rule (product_type_id, trigger_attribute_id,
                      trigger_option_id, target_attribute_id, rule_type),
  ...
)
```

**`product_type_id`** scopes the rule. "New vehicle has zero mileage" should
not fire on phones. Rules resolve along the type chain exactly like
attributes, so a rule on `VEHICLE` applies to `CAR` and `TRUCK` both.

**`trigger_option_id`** is a specific option, not just an attribute.
`condition = new` and `condition = used` are two different rules with two
different effects.

**`rule_value`** is `VARCHAR` because it holds different things per rule type —
`"0"` for `force_value`, `"100"` for `max`, `NULL` for `hide` and `require`.
Coerced at validation time using the target attribute's `data_type`.

**`message`** lets the administrator write the error text. Without it the
system produces generic messages, which undermines the point of
admin-configurable behaviour.

**The unique key includes `rule_type`**, so one trigger can both force a value
and hide a field.

---

## Rule types

| Type | Effect | `rule_value` |
|---|---|---|
| `force_value` | Set the target and lock the input | The forced value |
| `hide` | Remove the field entirely; drop any submitted value | — |
| `require` | Make an optional field required | — |
| `max` | Reject values above a bound | The upper bound |
| `min` | Reject values below a bound | The lower bound |

---

## The seeded rules

| Scope | Trigger | Target | Type | Value |
|---|---|---|---|---|
| `VEHICLE` | condition = new | mileage_km | `force_value` | 0 |
| `VEHICLE` | condition = used | mileage_km | `min` | 1 |
| `MOBILE_PHONE` | condition = new | warranty_months | `require` | — |
| `MOBILE_PHONE` | condition = used | warranty_months | `hide` | — |

Four rows. The two vehicle rules cover both cars and trucks with no
truck-specific entry.

### The required-flag interaction

`mileage_km` is bound to `VEHICLE` as **optional**, not required. This is
deliberate and non-obvious.

`validate()` runs before `apply_rules()`. If mileage were required at the type
level, a new car with an empty (locked) mileage field would be rejected before
the `force_value` rule could fill in the 0.

Making it optional lets validation pass, then the rules decide: `force_value`
on new, `min: 1` on used. The rules are more precise than a blanket required
flag — which is the point of having them.

---

## Server-side enforcement

```python
def apply_rules(definitions, cleaned, rules):
    for trigger_code, by_option in rules.items():
        selected = cleaned.get(trigger_code)
        if selected is None:
            continue
        for rule in by_option.get(selected, []):
            ...
```

Runs after `validate()`, before the transaction opens.

Behaviour per type:

- **`force_value`** fills a missing value rather than rejecting it, because a
  read-only input submits nothing. If a *different* value arrives, it is
  rejected.
- **`hide`** silently drops the value. A hidden field's data should not be
  stored even if posted.
- **`require`**, **`max`**, **`min`** raise `ValidationError` with the
  administrator's message.

---

## Client-side application

`app/static/cascade.js` reads the rules from a `data-rules` attribute on the
body tag and binds to any trigger field present in the form.

```javascript
const evaluate = () => {
  allTargets.forEach(resetTarget);
  const active = rules[triggerCode][trigger.value] || [];
  active.forEach(applyRule);
};
trigger.addEventListener('change', evaluate);
evaluate();   // also on load
```

**`resetTarget` runs before applying.** Switching from New to Used must
un-lock the mileage field and remove its note. Without the reset, rules stick
permanently — the same failure mode as a cascade that does not clear its
child.

`data-originallyRequired` is captured once on load so `resetTarget` can
restore the original required state rather than blanket-clearing it.

`evaluate()` also runs on load, so a form re-rendered after a validation error
re-applies the rules for the already-selected condition.

The JS knows nothing about cars or phones. It reads `data-field` wrappers and
applies whatever the registry returned.

---

## Verification

| Test | Result |
|---|---|
| Car, condition = New | Mileage set to 0, read-only, message shown |
| Switch to Used | Field unlocks, message changes |
| Save used car with mileage 0 | Rejected: "A used vehicle must have recorded mileage." |
| **Truck, condition = New** | **Mileage locks — no truck-specific rule exists** |
| Phone, condition = New | Warranty becomes required |
| Phone, condition = Used | Warranty field disappears |
| API POST, condition = new, mileage = 50000 | Rejected 400 |

The truck test is the architectural proof: rules resolve along the type chain,
so one `VEHICLE` row covers every vehicle type present and future.

---

## Two bugs worth recording

Both failed **silently** rather than erroring, which is what made them
instructive.

### 1. The optional-parameter trap

`create_product(..., rules=None)` was called from two places. One passed
rules; the debug API endpoint did not. The result: a new car with 50,000 km
saved successfully through the API while the form correctly rejected it.

The bypass test caught it. Without that test the system would have looked
correct while enforcing nothing on one of its two entry points.

**A stricter design would make `rules` a required parameter**, converting a
silent skip into an immediate `TypeError`.

### 2. Dict keys across a serialisation boundary

The resolver returns rules keyed by `trigger_option_id`, an **integer** from
MySQL.

- **Python** receives that dict directly — keys stay integers
- **JavaScript** receives it as JSON, where object keys are always **strings**

`apply_rules` initially looked up `str(selected)`, found nothing, and applied
no rules. The lookup returned an empty list rather than raising.

A closely related bug appeared in the form template: submitted form values are
strings while `opt.id` is an integer, so `value == opt.id` was always false
and a form re-rendered after a validation error lost all its selections. Fixed
with `value|string == opt.id|string`.

**General lesson:** the resolver's output serves both a Python consumer and a
JSON one, and dict key types do not survive that boundary identically. Both
bugs presented as "nothing happens" rather than an exception.

---

## Not implemented

**Numeric triggers.** Rules fire on option values only. "If year < 2000
then..." would require comparison operators in the trigger, doubling the
design surface.

**Multi-condition triggers.** One trigger attribute per rule. "If new AND
imported" is not expressible.

**An admin UI.** Rules are created via the seed script or SQL.

**Realism caveat on the seeded rule.** Dealers routinely list new cars with
10–50 km of delivery mileage, so `force_value: 0` is stricter than reality.
The correct production rule would be `max: 100`, which the table already
supports — `rule_type` is an enum and `max` is implemented. The stricter rule
was kept because it demonstrates `force_value`, the type with the most visible
UI effect.
