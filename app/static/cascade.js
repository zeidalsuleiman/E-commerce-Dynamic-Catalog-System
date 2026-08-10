document.addEventListener('DOMContentLoaded', () => {
  const typeId = document.body.dataset.productTypeId;
  const dependents = document.querySelectorAll('[data-depends-on]');

  dependents.forEach(child => {
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
});