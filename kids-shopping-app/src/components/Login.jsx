import { useState } from 'react'

const PARENTS = [
  { id: 'p1', label: 'Anoojan', emoji: '👨🏽‍💻' },
  { id: 'p2', label: 'Mom', emoji: '👩🏽' },
]

export default function Login({ onDone }) {
  const [who, setWho] = useState(null)
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [err, setErr] = useState('')

  const submit = (e) => {
    e.preventDefault()
    const finalName = (name || PARENTS.find((p) => p.id === who)?.label || '').trim()
    if (!who || !finalName) return setErr('Pick who you are first!')
    if (pin.trim().length < 4) return setErr('Enter the 4-digit family PIN.')
    onDone({ id: who, name: finalName, pin: pin.trim() })
  }

  return (
    <div className="login">
      <div className="login-card">
        <div className="login-art">🎒✏️📚</div>
        <h1>Back to School HQ</h1>
        <p className="login-sub">
          One shared shopping list for Aiden &amp; Aliya — pick who you are to jump in.
        </p>
        <form onSubmit={submit}>
          <div className="who-row">
            {PARENTS.map((p) => (
              <button
                type="button"
                key={p.id}
                className={`who ${who === p.id ? 'active' : ''}`}
                onClick={() => setWho(p.id)}
              >
                <span>{p.emoji}</span>
                {p.label}
              </button>
            ))}
          </div>
          {who === 'p2' && (
            <input
              className="text-input"
              placeholder="Your name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
          <input
            className="text-input"
            placeholder="Family PIN"
            inputMode="numeric"
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
          />
          {err && <div className="login-err">{err}</div>}
          <button className="cta" type="submit">
            Start shopping →
          </button>
        </form>
        <p className="login-fine">
          The PIN keeps the shared list private to your family. Wrong PIN still lets you browse,
          but the list won't sync between devices.
        </p>
      </div>
    </div>
  )
}
