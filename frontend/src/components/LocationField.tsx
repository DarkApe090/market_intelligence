import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { MapPin } from 'lucide-react'
import { request } from '../lib/api'

type Place = { label: string, name: string, country: string, kind: 'city' | 'country' }

export function LocationField({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const [query, setQuery] = useState(value)
  const [options, setOptions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const box = useRef<HTMLLabelElement>(null)

  useEffect(() => {
    if (!open) setQuery(value)
  }, [value, open])

  useEffect(() => {
    if (!open) return
    const q = query.trim() || value
    if (q.length < 2) {
      setOptions([])
      return
    }
    const timer = window.setTimeout(() => {
      void request<Place[]>(`/career-profile/places?q=${encodeURIComponent(q)}`)
        .then((places) => {
          setOptions(places)
          setActive(0)
        })
        .catch(() => setOptions([]))
    }, 280)
    return () => window.clearTimeout(timer)
  }, [query, open, value])

  useEffect(() => {
    function close(event: MouseEvent) {
      if (box.current && !box.current.contains(event.target as Node)) {
        setQuery(value)
        setOpen(false)
      }
    }
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [value])

  function choose(place: Place) {
    onChange(place.label)
    setQuery(place.label)
    setOpen(false)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setQuery(value)
      setOpen(false)
      return
    }
    if (!options.length) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((current) => (current + 1) % options.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((current) => (current - 1 + options.length) % options.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      choose(options[active])
    }
  }

  return (
    <label className="cv-location-field" ref={box}>
      <MapPin size={16} />
      <input
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setOpen(true)
        }}
        onFocus={() => {
          setQuery(value)
          setOpen(true)
        }}
        onKeyDown={onKeyDown}
        aria-label="Localização da vaga"
        placeholder="Escolhe cidade ou país"
        autoComplete="off"
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls="place-options"
        aria-autocomplete="list"
        aria-activedescendant={open && options[active] ? `place-option-${active}` : undefined}
      />
      {open && options.length > 0 && (
        <ul className="place-menu" id="place-options" role="listbox">
          {options.map((place, index) => (
            <li key={place.label} id={`place-option-${index}`}>
              <button
                type="button"
                role="option"
                aria-selected={index === active}
                className={index === active ? 'is-active' : undefined}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(place)}
              >
                {place.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </label>
  )
}
