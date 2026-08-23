// Curated back-to-school starter catalog. Prices are typical CAD prices for
// these item types; live price/stock is always confirmed on the retailer site
// via each card's link, which opens a size-appropriate search on the Canadian
// store. `query` overrides the search text when the display name is too fancy.
//
// Tuple: [kid, retailer, category, name, emoji, price, salePrice, colors, tag, query?]
const T = (kid, retailer, category, name, emoji, price, salePrice, colors, tag, query) => ({
  kid, retailer, category, name, emoji, price, salePrice, colors, tag, query,
})

const ITEMS = [
  // ------------------------- AIDEN (boy, size 7) -------------------------
  // Old Navy
  T('aiden', 'oldnavy', 'tops', 'Graphic Tee 3-Pack', '👕', 34.99, 24.99, ['multi'], 'deal', 'graphic t-shirt pack'),
  T('aiden', 'oldnavy', 'tops', 'Long-Sleeve Henley', '👕', 19.99, null, ['navy', 'grey'], null, 'long sleeve henley'),
  T('aiden', 'oldnavy', 'bottoms', 'Slim Built-In Flex Jeans', '👖', 39.99, 29.99, ['denim'], 'bestseller', 'slim jeans'),
  T('aiden', 'oldnavy', 'bottoms', 'Jogger Sweatpants 2-Pack', '👖', 32.99, null, ['grey', 'black'], null, 'jogger sweatpants'),
  T('aiden', 'oldnavy', 'outerwear', 'Water-Resistant Hooded Jacket', '🧥', 49.99, null, ['navy', 'green'], null, 'hooded jacket'),
  T('aiden', 'oldnavy', 'activewear', 'Go-Dry Mesh Shorts', '🩳', 16.99, 12.99, ['blue', 'black'], 'deal', 'mesh shorts'),
  // H&M
  T('aiden', 'hm', 'tops', 'Cotton Tee 5-Pack', '👕', 29.99, null, ['multi'], 'bestseller', 'cotton t-shirts 5-pack'),
  T('aiden', 'hm', 'tops', 'Printed Hoodie', '🧢', 24.99, null, ['grey', 'green'], null, 'printed hoodie'),
  T('aiden', 'hm', 'bottoms', 'Pull-On Cargo Pants', '👖', 29.99, null, ['khaki', 'black'], 'new', 'cargo pants'),
  T('aiden', 'hm', 'bottoms', 'Sweatpants 2-Pack', '👖', 27.99, 19.99, ['navy', 'grey'], 'deal', 'sweatpants 2-pack'),
  T('aiden', 'hm', 'sleepwear', 'Dino Pyjama Set', '🦕', 19.99, null, ['green'], null, 'dinosaur pyjamas'),
  T('aiden', 'hm', 'accessories', 'Sock 7-Pack', '🧦', 14.99, null, ['multi'], null, 'socks 7-pack'),
  // Zara
  T('aiden', 'zara', 'tops', 'Textured Polo Shirt', '👕', 25.9, null, ['white', 'navy'], 'new', 'polo shirt'),
  T('aiden', 'zara', 'tops', 'Crewneck Sweatshirt', '👕', 29.9, null, ['grey', 'blue'], null, 'crewneck sweatshirt'),
  T('aiden', 'zara', 'bottoms', 'Relaxed-Fit Chinos', '👖', 35.9, null, ['khaki', 'navy'], null, 'chino pants'),
  T('aiden', 'zara', 'outerwear', 'Quilted Puffer Vest', '🧥', 45.9, null, ['navy', 'black'], 'new', 'puffer vest'),
  T('aiden', 'zara', 'shoes', 'Chunky-Sole Sneakers', '👟', 49.9, null, ['white'], null, 'sneakers'),
  T('aiden', 'zara', 'accessories', 'Canvas Backpack', '🎒', 39.9, null, ['navy', 'green'], null, 'backpack'),
  // OshKosh
  T('aiden', 'oshkosh', 'tops', 'Plaid Button-Front Shirt', '👕', 34.0, 22.0, ['red', 'blue'], 'deal', 'plaid shirt'),
  T('aiden', 'oshkosh', 'bottoms', 'Classic Denim Overalls', '👖', 48.0, 33.6, ['denim'], 'bestseller', 'denim overalls'),
  T('aiden', 'oshkosh', 'bottoms', 'Stretch Uniform Chinos', '👖', 36.0, 25.2, ['khaki', 'navy'], 'deal', 'uniform chino pants'),
  T('aiden', 'oshkosh', 'outerwear', 'Fleece Zip Hoodie', '🧥', 38.0, null, ['blue', 'grey'], null, 'fleece zip hoodie'),
  T('aiden', 'oshkosh', 'sleepwear', 'Space 4-Piece PJ Set', '🚀', 44.0, 30.8, ['navy'], 'deal', 'space pajamas'),
  T('aiden', 'oshkosh', 'accessories', 'Kids Bucket Hat', '🧢', 20.0, null, ['khaki'], null, 'bucket hat'),
  // Joe Fresh
  T('aiden', 'joefresh', 'tops', 'Essential Tee 3-Pack', '👕', 19.0, null, ['multi'], 'deal', 't-shirt 3-pack'),
  T('aiden', 'joefresh', 'bottoms', 'Pull-On Denim Jogger', '👖', 24.0, null, ['denim'], null, 'denim jogger'),
  T('aiden', 'joefresh', 'activewear', 'Active Tee + Short Set', '🩳', 22.0, 16.0, ['blue', 'black'], 'deal', 'active set'),
  T('aiden', 'joefresh', 'outerwear', 'Rain Shell Jacket', '🧥', 39.0, null, ['yellow', 'navy'], null, 'rain jacket'),
  T('aiden', 'joefresh', 'shoes', 'Velcro Running Shoes', '👟', 24.0, null, ['blue', 'black'], null, 'running shoes'),
  T('aiden', 'joefresh', 'accessories', 'Underwear 5-Pack', '🩲', 15.0, null, ['multi'], null, 'boys underwear 5-pack'),
  // Walmart
  T('aiden', 'walmart', 'tops', 'George Tee 4-Pack', '👕', 16.98, null, ['multi'], 'deal', 't-shirt 4-pack'),
  T('aiden', 'walmart', 'bottoms', 'Athletic Works Joggers', '👖', 12.98, null, ['grey', 'navy'], 'bestseller', 'athletic joggers'),
  T('aiden', 'walmart', 'shoes', 'Light-Up Sneakers', '👟', 29.97, 24.97, ['black', 'blue'], 'deal', 'light up sneakers'),
  T('aiden', 'walmart', 'accessories', 'Marvel Backpack + Lunch Bag', '🎒', 34.97, null, ['multi'], 'bestseller', 'backpack lunch bag set'),
  T('aiden', 'walmart', 'accessories', 'Bento Lunch Box', '🍱', 14.97, null, ['blue', 'green'], null, 'kids bento lunch box'),
  T('aiden', 'walmart', 'outerwear', 'Mid-Weight Puffer Jacket', '🧥', 39.97, null, ['navy', 'red'], null, 'puffer jacket'),

  // ------------------------- ALIYA (girl, size 3-4) -------------------------
  // Old Navy
  T('aliya', 'oldnavy', 'tops', 'Graphic Tee 3-Pack', '👚', 32.99, 22.99, ['multi'], 'deal', 'toddler graphic tee pack'),
  T('aliya', 'oldnavy', 'dresses', 'Fit & Flare Jersey Dress', '👗', 24.99, null, ['pink', 'purple'], 'bestseller', 'jersey dress'),
  T('aliya', 'oldnavy', 'bottoms', 'Leggings 3-Pack', '👖', 26.99, 19.99, ['multi'], 'deal', 'leggings 3-pack'),
  T('aliya', 'oldnavy', 'outerwear', 'Cozy Teddy Zip Jacket', '🧥', 39.99, null, ['pink', 'white'], null, 'teddy jacket'),
  T('aliya', 'oldnavy', 'sleepwear', 'Snug-Fit PJ 2-Pack', '🌙', 29.99, null, ['pink', 'purple'], null, 'pajama set'),
  T('aliya', 'oldnavy', 'accessories', 'Bow Sock 6-Pack', '🧦', 12.99, null, ['multi'], null, 'toddler socks'),
  // H&M
  T('aliya', 'hm', 'dresses', 'Tulle-Skirt Dress', '👗', 29.99, null, ['pink'], 'new', 'tulle dress'),
  T('aliya', 'hm', 'tops', 'Puff-Sleeve Top 2-Pack', '👚', 19.99, null, ['pink', 'white'], null, 'puff sleeve top'),
  T('aliya', 'hm', 'bottoms', 'Treggings 2-Pack', '👖', 24.99, 17.99, ['purple', 'black'], 'deal', 'treggings'),
  T('aliya', 'hm', 'outerwear', 'Hooded Cardigan', '🧥', 24.99, null, ['pink', 'grey'], null, 'hooded cardigan'),
  T('aliya', 'hm', 'sleepwear', 'Unicorn Pyjama Set', '🦄', 19.99, null, ['purple'], 'bestseller', 'unicorn pyjamas'),
  T('aliya', 'hm', 'accessories', 'Hair Clip 10-Pack', '🎀', 9.99, null, ['multi'], null, 'hair clips'),
  // Zara
  T('aliya', 'zara', 'dresses', 'Corduroy Pinafore Dress', '👗', 35.9, null, ['red', 'navy'], 'new', 'pinafore dress'),
  T('aliya', 'zara', 'tops', 'Ribbed Turtleneck 2-Pack', '👚', 25.9, null, ['white', 'pink'], null, 'ribbed turtleneck'),
  T('aliya', 'zara', 'bottoms', 'Paperbag Waist Jeans', '👖', 35.9, null, ['denim'], null, 'paperbag jeans'),
  T('aliya', 'zara', 'outerwear', 'Faux-Shearling Coat', '🧥', 59.9, null, ['white', 'pink'], 'new', 'shearling coat'),
  T('aliya', 'zara', 'shoes', 'Glitter Mary Janes', '👟', 39.9, null, ['pink'], null, 'mary jane shoes'),
  T('aliya', 'zara', 'accessories', 'Mini Heart Backpack', '🎒', 35.9, null, ['red', 'pink'], null, 'backpack'),
  // OshKosh
  T('aliya', 'oshkosh', 'dresses', 'Floral Corduroy Jumper', '👗', 40.0, 28.0, ['purple'], 'deal', 'corduroy jumper dress'),
  T('aliya', 'oshkosh', 'tops', 'Ruffle Tee 2-Pack', '👚', 28.0, 19.6, ['pink', 'white'], 'deal', 'ruffle tee'),
  T('aliya', 'oshkosh', 'bottoms', 'Classic Denim Overalls', '👖', 48.0, 33.6, ['denim'], 'bestseller', 'denim overalls'),
  T('aliya', 'oshkosh', 'outerwear', 'Sherpa-Lined Jacket', '🧥', 55.0, 38.5, ['pink'], 'deal', 'sherpa jacket'),
  T('aliya', 'oshkosh', 'sleepwear', 'Rainbow 4-Piece PJ Set', '🌈', 44.0, 30.8, ['multi'], 'deal', 'rainbow pajamas'),
  T('aliya', 'oshkosh', 'accessories', 'Toddler Backpack', '🎒', 36.0, null, ['pink', 'purple'], null, 'toddler backpack'),
  // Joe Fresh
  T('aliya', 'joefresh', 'tops', 'Essential Tee 3-Pack', '👚', 17.0, null, ['multi'], 'deal', 'toddler tee 3-pack'),
  T('aliya', 'joefresh', 'dresses', 'Knit Skater Dress', '👗', 19.0, null, ['pink', 'navy'], null, 'skater dress'),
  T('aliya', 'joefresh', 'bottoms', 'Legging 2-Pack', '👖', 15.0, null, ['pink', 'black'], 'bestseller', 'toddler leggings'),
  T('aliya', 'joefresh', 'outerwear', 'Quilted Jacket', '🧥', 34.0, 24.0, ['purple', 'pink'], 'deal', 'quilted jacket'),
  T('aliya', 'joefresh', 'shoes', 'Glitter Sneakers', '👟', 19.0, null, ['pink', 'white'], null, 'toddler sneakers'),
  T('aliya', 'joefresh', 'accessories', 'Tights 3-Pack', '🧦', 12.0, null, ['multi'], null, 'toddler tights'),
  // Walmart
  T('aliya', 'walmart', 'dresses', 'George Tutu Dress', '👗', 14.98, null, ['pink', 'purple'], 'deal', 'tutu dress'),
  T('aliya', 'walmart', 'tops', 'Long-Sleeve Tee 3-Pack', '👚', 14.98, null, ['multi'], null, 'toddler long sleeve tee'),
  T('aliya', 'walmart', 'bottoms', 'Jogger 2-Pack', '👖', 12.98, null, ['pink', 'grey'], 'bestseller', 'toddler joggers'),
  T('aliya', 'walmart', 'shoes', 'Light-Up Runners', '👟', 24.97, 19.97, ['pink'], 'deal', 'toddler light up shoes'),
  T('aliya', 'walmart', 'accessories', 'Paw Patrol Backpack Set', '🎒', 29.97, null, ['multi'], 'bestseller', 'paw patrol backpack'),
  T('aliya', 'walmart', 'outerwear', 'Hooded Puffer Jacket', '🧥', 34.97, null, ['purple', 'pink'], null, 'toddler puffer jacket'),
]

export const CATALOG = ITEMS.map((item, i) => ({ ...item, id: `p${i + 1}` }))

export const CATEGORIES = [
  { id: 'tops', label: 'Tops', emoji: '👕' },
  { id: 'bottoms', label: 'Bottoms', emoji: '👖' },
  { id: 'dresses', label: 'Dresses', emoji: '👗' },
  { id: 'outerwear', label: 'Outerwear', emoji: '🧥' },
  { id: 'activewear', label: 'Active', emoji: '🩳' },
  { id: 'sleepwear', label: 'Sleepwear', emoji: '🌙' },
  { id: 'shoes', label: 'Shoes', emoji: '👟' },
  { id: 'accessories', label: 'Accessories', emoji: '🎒' },
]

export const COLOR_SWATCHES = {
  navy: '#1e3a5f', blue: '#3b82f6', black: '#1f2937', grey: '#9ca3af',
  white: '#f9fafb', red: '#ef4444', pink: '#f472b6', purple: '#a78bfa',
  green: '#34d399', yellow: '#fbbf24', khaki: '#b8a878', denim: '#4a6da7',
  multi: 'linear-gradient(135deg,#f472b6,#fbbf24,#34d399,#3b82f6)',
}
