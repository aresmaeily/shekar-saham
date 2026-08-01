/**
 * support_resistance.js - حمایت/مقاومت خودکار (ایده ۴.۱)
 * تشخیص نقاط چرخش (swing high/low) و رسم خطوط حمایت/مقاومت افقی روی چارت
 */
export function findSupportResistance(data, { window = 5, clusterPct = 0.15 } = {}) {
  if (!Array.isArray(data) || data.length < window * 2 + 2) return { supports: [], resistances: [] };

  const swings = [];
  for (let i = window; i < data.length - window; i++) {
    const c = data[i];
    let isHigh = true;
    let isLow = true;
    for (let j = i - window; j <= i + window; j++) {
      if (j === i) continue;
      if (data[j].high >= c.high) isHigh = false;
      if (data[j].low <= c.low) isLow = false;
    }
    if (isHigh) swings.push({ price: c.high, type: "res" });
    if (isLow) swings.push({ price: c.low, type: "sup" });
  }

  // خوشه‌بندی ساده: نقاط نزدیک را با میانگین ترکیب کن
  const cluster = (points) => {
    const groups = [];
    for (const p of points) {
      let g = groups.find((x) => Math.abs(x.price - p.price) / p.price < clusterPct);
      if (g) {
        g.price = (g.price * g.count + p.price) / (g.count + 1);
        g.count++;
      } else {
        groups.push({ price: p.price, count: 1 });
      }
    }
    return groups
      .filter((g) => g.count >= 2)
      .sort((a, b) => b.count - a.count)
      .slice(0, 4)
      .map((g) => g.price);
  };

  return {
    supports: cluster(swings.filter((s) => s.type === "sup")),
    resistances: cluster(swings.filter((s) => s.type === "res")),
  };
}
