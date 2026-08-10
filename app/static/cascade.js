document.addEventListener('DOMContentLoaded', () => {
  const typeId = document.body.dataset.productTypeId;
  const rules = JSON.parse(document.body.dataset.rules || '{}');

  // ------------------------------------------------------------------
  // Cascading dependent dropdowns (make -> model)
  // Binds to any field the resolver reported a dependency for.
  // ------------------------------------------------------------------
  document.querySelectorAll('[data-depends-on]').forEach(child => {
    const parentCode = child.dataset.dependsOn;
    const parent = document.querySelector(`[name="${parentCode}"]`);
    if (!parent) return;

    parent.addEventListener('change', async () => {
      child.innerHTML = '<option value="">Loading…</option>';
      child.disabled = true;

      if (!parent.value) {
        child.innerHTML = `<option value="">Select ${parentCode} first</option>`;
        return;
      }

      const url = `/api/options/${child.name}`
                + `?parent_option_id=${parent.value}`
                + `&product_type_id=${typeId}`;

      try {
        const res = await fetch(url);
        const data = await res.json();

        child.innerHTML = '<option value="">Choose…</option>';
        data.options.forEach(o => {
          const opt = document.createElement('option');
          opt.value = o.id;
          opt.textContent = o.label;
          child.appendChild(opt);
        });
        child.disabled = data.options.length === 0;
        if (data.options.length === 0) {
          child.innerHTML = '<option value="">No options available</option>';
        }
      } catch (err) {
        child.innerHTML = '<option value="">Failed to load</option>';
      }
    });
  });

  // ------------------------------------------------------------------
  // Constraint rules (condition=new -> mileage forced to 0, etc.)
  // Rules come from the registry; this code knows nothing about cars
  // or phones.
  // ------------------------------------------------------------------
  function fieldWrapper(code) {
    return document.querySelector(`[data-field="${code}"]`);
  }

  function resetTarget(code) {
    const wrap = fieldWrapper(code);
    if (!wrap) return;

    const input = wrap.querySelector('input, select');
    wrap.style.display = '';
    if (input) {
      input.readOnly = false;
      input.required = input.dataset.originallyRequired === 'true';
      input.classList.remove('bg-light');
      input.removeAttribute('max');
      input.removeAttribute('min');
    }
    const note = wrap.querySelector('.rule-note');
    if (note) note.remove();
  }

  function applyRule(rule) {
    const wrap = fieldWrapper(rule.target_code);
    if (!wrap) return;

    const input = wrap.querySelector('input, select');

    if (rule.rule_type === 'hide') {
      wrap.style.display = 'none';
      if (input) {
        input.value = '';
        input.required = false;
      }
      return;
    }

    if (input) {
      if (rule.rule_type === 'force_value') {
        input.value = rule.rule_value;
        input.readOnly = true;
        input.classList.add('bg-light');
      }
      if (rule.rule_type === 'require') input.required = true;
      if (rule.rule_type === 'max') input.max = rule.rule_value;
      if (rule.rule_type === 'min') input.min = rule.rule_value;
    }

    if (rule.message && !wrap.querySelector('.rule-note')) {
      const note = document.createElement('div');
      note.className = 'form-text rule-note text-muted';
      note.textContent = rule.message;
      wrap.appendChild(note);
    }
  }

  // Remember which fields were required before any rule touched them,
  // so resetTarget can restore the original state.
  document.querySelectorAll('[data-field] input, [data-field] select')
    .forEach(el => { el.dataset.originallyRequired = el.required; });

  Object.keys(rules).forEach(triggerCode => {
    const trigger = document.querySelector(`[name="${triggerCode}"]`);
    if (!trigger) return;

    const allTargets = new Set();
    Object.values(rules[triggerCode]).forEach(list =>
      list.forEach(r => allTargets.add(r.target_code))
    );

    const evaluate = () => {
      allTargets.forEach(resetTarget);
      const active = rules[triggerCode][String(trigger.value)] || [];
      active.forEach(applyRule);
    };

    trigger.addEventListener('change', evaluate);
    evaluate();   // apply on load, in case a value is already selected
  });
});