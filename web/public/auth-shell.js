/**
 * Popup selects for OAuth / auth HTML (parity with shadcn Base UI Select in the SPA).
 * Enhances native <select> inside .auth-layout for form posts; keeps a hidden native control in sync.
 */
(function () {
  var CHEVRON =
    '<svg class="hub-select-chevron" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>'

  function optionLabel(select, value) {
    for (var i = 0; i < select.options.length; i++) {
      var opt = select.options[i]
      if (opt.value === value) return opt.textContent || ''
    }
    return ''
  }

  function enhanceSelect(select) {
    if (select.dataset.hubSelectEnhanced === '1') return
    if (select.multiple) return
    select.dataset.hubSelectEnhanced = '1'

    var root = document.createElement('div')
    root.className = 'hub-select'

    var trigger = document.createElement('button')
    trigger.type = 'button'
    trigger.className = 'hub-select-trigger'
    trigger.setAttribute('aria-haspopup', 'listbox')
    trigger.setAttribute('aria-expanded', 'false')

    var valueEl = document.createElement('span')
    valueEl.className = 'hub-select-value'
    trigger.appendChild(valueEl)
    trigger.insertAdjacentHTML('beforeend', CHEVRON)

    var popup = document.createElement('div')
    popup.className = 'hub-select-content'
    popup.hidden = true

    var list = document.createElement('div')
    list.className = 'hub-select-list'
    list.setAttribute('role', 'listbox')

    var options = []
    for (var i = 0; i < select.options.length; i++) {
      ;(function (opt) {
        var item = document.createElement('div')
        item.className = 'hub-select-item'
        item.setAttribute('role', 'option')
        item.dataset.value = opt.value
        item.textContent = opt.textContent || ''
        if (opt.disabled) {
          item.setAttribute('aria-disabled', 'true')
          item.classList.add('is-disabled')
        }
        item.addEventListener('click', function () {
          if (opt.disabled) return
          setValue(opt.value)
          close()
        })
        list.appendChild(item)
        options.push(item)
      })(select.options[i])
    }
    popup.appendChild(list)

    select.classList.add('hub-select-native')
    select.tabIndex = -1
    select.setAttribute('aria-hidden', 'true')

    if (select.id) {
      trigger.id = select.id + '-trigger'
      var label = document.querySelector('label[for="' + select.id.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"]')
      if (label) label.setAttribute('for', trigger.id)
    }

    select.parentNode.insertBefore(root, select)
    root.appendChild(select)
    root.appendChild(trigger)
    root.appendChild(popup)

    var open = false
    var activeIndex = -1

    function syncFromNative() {
      var val = select.value
      valueEl.textContent = optionLabel(select, val)
      for (var j = 0; j < options.length; j++) {
        var selected = options[j].dataset.value === val
        options[j].setAttribute('aria-selected', selected ? 'true' : 'false')
        if (selected) activeIndex = j
      }
      if (!valueEl.textContent && select.options.length) {
        var ph = select.querySelector('option[value=""]')
        if (ph) valueEl.textContent = ph.textContent || ''
        valueEl.classList.add('is-placeholder')
      } else {
        valueEl.classList.remove('is-placeholder')
      }
    }

    function setValue(value) {
      select.value = value
      select.dispatchEvent(new Event('change', { bubbles: true }))
      syncFromNative()
    }

    function openList() {
      if (select.disabled) return
      open = true
      popup.hidden = false
      trigger.setAttribute('aria-expanded', 'true')
      syncFromNative()
      if (activeIndex >= 0 && options[activeIndex]) {
        options[activeIndex].scrollIntoView({ block: 'nearest' })
      }
    }

    function close() {
      open = false
      popup.hidden = true
      trigger.setAttribute('aria-expanded', 'false')
    }

    function toggle() {
      if (open) close()
      else openList()
    }

    trigger.addEventListener('click', function (e) {
      e.preventDefault()
      toggle()
    })

    document.addEventListener('click', function (e) {
      if (!root.contains(e.target)) close()
    })

    trigger.addEventListener('keydown', function (e) {
      if (select.disabled) return
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        if (!open) {
          openList()
          return
        }
      }
      if (!open) return
      if (e.key === 'Escape') {
        e.preventDefault()
        close()
        trigger.focus()
        return
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        do {
          activeIndex = Math.min(options.length - 1, activeIndex + 1)
        } while (options[activeIndex] && options[activeIndex].getAttribute('aria-disabled') === 'true')
        options[activeIndex].scrollIntoView({ block: 'nearest' })
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        do {
          activeIndex = Math.max(0, activeIndex - 1)
        } while (options[activeIndex] && options[activeIndex].getAttribute('aria-disabled') === 'true')
        options[activeIndex].scrollIntoView({ block: 'nearest' })
      }
      if (e.key === 'Enter' && activeIndex >= 0 && options[activeIndex]) {
        e.preventDefault()
        if (options[activeIndex].getAttribute('aria-disabled') !== 'true') {
          setValue(options[activeIndex].dataset.value)
          close()
          trigger.focus()
        }
      }
    })

    if (select.disabled) {
      trigger.disabled = true
    }

    select.addEventListener('change', syncFromNative)
    syncFromNative()
  }

  function init() {
    document.querySelectorAll('.auth-layout select').forEach(enhanceSelect)
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()
