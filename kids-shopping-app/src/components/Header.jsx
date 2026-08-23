import { KIDS, KID_IDS } from '../data/kids.js'

const SYNC_LABEL = {
  local: { text: 'Local only', dot: '#f59e0b', title: 'Changes saved on this device; sync unavailable' },
  syncing: { text: 'Syncing…', dot: '#3b82f6', title: 'Talking to the shared list' },
  synced: { text: 'Synced', dot: '#22c55e', title: 'Shared list is up to date' },
  'bad-pin': { text: 'Wrong PIN', dot: '#ef4444', title: 'Sign out and re-enter the family PIN to sync' },
}

export default function Header({
  profile, kid, kidId, kidCounts, onKid, listCount, syncState, onOpenList, onSignOut,
}) {
  const sync = SYNC_LABEL[syncState] || SYNC_LABEL.local
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-logo">🎒</span>
        <div>
          <h1>Back to School HQ</h1>
          <div className="brand-sub">
            Hi {profile.name}!{' '}
            <span className="sync" title={sync.title}>
              <i style={{ background: sync.dot }} /> {sync.text}
            </span>
            <button className="linkish" onClick={onSignOut}>switch user</button>
          </div>
        </div>
      </div>

      <div className="kid-toggle" role="tablist" aria-label="Choose kid">
        {KID_IDS.map((id) => {
          const k = KIDS[id]
          return (
            <button
              key={id}
              role="tab"
              aria-selected={kidId === id}
              className={`kid-tab ${kidId === id ? 'active' : ''}`}
              style={{ '--kc': k.accent, '--ks': k.accentSoft }}
              onClick={() => onKid(id)}
            >
              <span className="kid-emoji">{k.emoji}</span>
              <span className="kid-meta">
                <b>{k.name}</b>
                <small>
                  {k.age} yrs · size {k.clothingSize}
                  {kidCounts[id] > 0 && <em> · {kidCounts[id]} picked</em>}
                </small>
              </span>
            </button>
          )
        })}
      </div>

      <button className="list-btn" onClick={onOpenList}>
        🛒 Our list
        {listCount > 0 && <span className="badge">{listCount}</span>}
      </button>

      <div className="size-banner" style={{ background: kid.accentSoft }}>
        <b>{kid.name}</b> turns {kid.turning} on {kid.birthday} — {kid.sizeLabel}
      </div>
    </header>
  )
}
