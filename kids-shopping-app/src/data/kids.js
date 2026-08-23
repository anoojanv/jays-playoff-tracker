// Kid profiles. Sizes are the "buy now" recommendation with growth headroom:
// Aiden turns 6 on Sept 25, so size 7 fits now and 8 is the size-up option.
// Aliya turns 4 on Dec 23, so 4/4T fits now (labels vary: 3-4 at H&M/Zara).
export const KIDS = {
  aiden: {
    id: 'aiden',
    name: 'Aiden',
    emoji: '🦖',
    gender: 'boy',
    age: 5,
    birthday: 'Sept 25',
    turning: 6,
    clothingSize: '7',
    sizeUp: '8',
    sizeLabel: 'Size 7 (buy 7–8 for growth)',
    shoeNote: 'Kids shoe size — check his current pair before ordering',
    searchWord: 'boys',
    accent: '#2563eb',
    accentSoft: '#dbeafe',
  },
  aliya: {
    id: 'aliya',
    name: 'Aliya',
    emoji: '🦄',
    gender: 'girl',
    age: 3,
    birthday: 'Dec 23',
    turning: 4,
    clothingSize: '3-4',
    sizeUp: '4-5',
    sizeLabel: 'Size 3–4 / 4T (buy 4–5 for growth)',
    shoeNote: 'Toddler shoe size — check her current pair before ordering',
    searchWord: 'toddler girls',
    accent: '#db2777',
    accentSoft: '#fce7f3',
  },
}

export const KID_IDS = ['aiden', 'aliya']
