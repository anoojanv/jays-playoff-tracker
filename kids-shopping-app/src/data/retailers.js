// Canadian retailer definitions. Every outbound link is a live search on the
// retailer's Canadian site — search URLs survive site redesigns far better
// than category IDs, and stock/size availability is always checked on-site.
export const RETAILERS = {
  oldnavy: {
    id: 'oldnavy',
    name: 'Old Navy',
    short: 'ON',
    color: '#003764',
    bg: '#e8f1f8',
    home: 'https://oldnavy.gapcanada.ca/',
    search: (q) => `https://oldnavy.gapcanada.ca/browse/search.do?searchText=${encodeURIComponent(q)}`,
    cart: 'https://secure-oldnavy.gapcanada.ca/shopping-bag',
    sizeNote: { aiden: 'Size 7 or M (8)', aliya: 'Size 4T or 5T' },
  },
  hm: {
    id: 'hm',
    name: 'H&M',
    short: 'H&M',
    color: '#e50010',
    bg: '#fdeaea',
    home: 'https://www2.hm.com/en_ca/kids.html',
    search: (q) => `https://www2.hm.com/en_ca/search-results.html?q=${encodeURIComponent(q)}`,
    cart: 'https://www2.hm.com/en_ca/cart',
    sizeNote: { aiden: 'Size 6-7Y or 7-8Y', aliya: 'Size 3-4Y or 4-5Y' },
  },
  zara: {
    id: 'zara',
    name: 'Zara',
    short: 'ZR',
    color: '#1a1a1a',
    bg: '#efefef',
    home: 'https://www.zara.com/ca/',
    search: (q) => `https://www.zara.com/ca/en/search?searchTerm=${encodeURIComponent(q)}`,
    cart: 'https://www.zara.com/ca/en/shop/cart',
    sizeNote: { aiden: 'Size 6 or 7 (116-122 cm)', aliya: 'Size 3-4 (104 cm)' },
  },
  oshkosh: {
    id: 'oshkosh',
    name: "OshKosh B'gosh",
    short: 'OK',
    color: '#0054a6',
    bg: '#e7f0fa',
    home: 'https://www.cartersoshkosh.ca/',
    search: (q) => `https://www.cartersoshkosh.ca/search?q=${encodeURIComponent(q)}`,
    cart: 'https://www.cartersoshkosh.ca/cart',
    sizeNote: { aiden: 'Size 7 or 8', aliya: 'Size 4T or 5T' },
  },
  joefresh: {
    id: 'joefresh',
    name: 'Joe Fresh',
    short: 'JF',
    color: '#f47b20',
    bg: '#fdf0e4',
    home: 'https://www.joefresh.com/ca',
    search: (q) => `https://www.joefresh.com/ca/search?q=${encodeURIComponent(q)}`,
    cart: 'https://www.joefresh.com/ca/cart',
    sizeNote: { aiden: 'Size S (7) or M (8)', aliya: 'Size 4 or 5' },
  },
  walmart: {
    id: 'walmart',
    name: 'Walmart',
    short: 'WM',
    color: '#0071ce',
    bg: '#e6f1fb',
    home: 'https://www.walmart.ca/en',
    search: (q) => `https://www.walmart.ca/search?q=${encodeURIComponent(q)}`,
    cart: 'https://www.walmart.ca/cart',
    sizeNote: { aiden: 'Size 7 or 7-8', aliya: 'Size 4T or 5' },
  },
}

export const RETAILER_IDS = ['oldnavy', 'hm', 'zara', 'oshkosh', 'joefresh', 'walmart']

// Build the live-search URL for a catalog item for a given kid.
export function itemSearchUrl(item, kid) {
  const retailer = RETAILERS[item.retailer]
  return retailer.search(`${kid.searchWord} ${item.query || item.name}`)
}
