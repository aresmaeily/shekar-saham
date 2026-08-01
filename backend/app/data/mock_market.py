"""مولد داده دمو با ساختار واقعی نمادهای بورس تهران.

برای توسعه UI و تست الگوریتم وقتی TSETMC در دسترس نیست.
هر بار فراخوانی، قیمت/حجم با نویز تصادفی کمی تغییر می‌کند تا حس زنده بودن بدهد.
"""

from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime, timezone
from typing import List

from app.models.schemas import SymbolSnapshot

# نمادهای معروف + صنعت + پارامترهای بنیادی تقریبی
SEED_SYMBOLS = [
    # (l18, l30, cs, pe, eps_base, price, float_shares_b, sector_bias)
    ("فملی", "ملی صنایع مس ایران", "فلزات اساسی", 6.5, 1200, 7800, 80, 0.4),
    ("فولاد", "فولاد مبارکه اصفهان", "فلزات اساسی", 5.8, 900, 5200, 120, 0.3),
    ("کگل", "معدنی و صنعتی گل‌گهر", "استخراج کانه‌های فلزی", 7.2, 1100, 7900, 45, 0.35),
    ("کچاد", "معدنی و صنعتی چادرملو", "استخراج کانه‌های فلزی", 6.9, 1050, 7200, 40, 0.3),
    ("شپنا", "پالایش نفت اصفهان", "فراورده‌های نفتی", 4.5, 1500, 6800, 70, 0.2),
    ("شتران", "پالایش نفت تهران", "فراورده‌های نفتی", 4.9, 900, 4500, 55, 0.15),
    ("شبندر", "پالایش نفت بندرعباس", "فراورده‌های نفتی", 5.1, 1300, 6600, 60, 0.2),
    ("وبملت", "بانک ملت", "بانکها و موسسات اعتباری", 3.8, 800, 3050, 200, 0.1),
    ("وتجارت", "بانک تجارت", "بانکها و موسسات اعتباری", 4.2, 450, 1900, 180, -0.05),
    ("وبصادر", "بانک صادرات ایران", "بانکها و موسسات اعتباری", 4.0, 380, 1520, 160, -0.1),
    ("خودرو", "ایران خودرو", "خودرو و ساخت قطعات", 12.5, 120, 1500, 150, 0.5),
    ("خساپا", "سایپا", "خودرو و ساخت قطعات", 14.0, 80, 1120, 130, 0.45),
    ("خپارس", "پارس خودرو", "خودرو و ساخت قطعات", 18.0, 40, 720, 40, 0.3),
    ("رمپنا", "گروه مپنا", "عرضه برق، گاز، بخاروآب گرم", 8.5, 600, 5100, 50, 0.25),
    ("بپاس", "بیمه پاسارگاد", "بیمه و صندوق بازنشستگی", 9.0, 400, 3600, 30, 0.1),
    ("وغدیر", "سرمایه‌گذاری غدیر", "سرمایه‌گذاریها", 5.5, 2000, 11000, 35, 0.2),
    ("وصندوق", "سرمایه‌گذاری صندوق بازنشستگی", "سرمایه‌گذاریها", 6.0, 1500, 9000, 40, 0.15),
    ("پارسان", "نفت و گاز و پتروشیمی تأمین", "محصولات شیمیایی", 5.2, 1800, 9400, 45, 0.25),
    ("تاپیکو", "سر. نفت و گاز و پتروشیمی تأمین", "محصولات شیمیایی", 5.0, 1600, 8000, 50, 0.2),
    ("نوری", "پتروشیمی نوری", "محصولات شیمیایی", 6.8, 2200, 15000, 25, 0.3),
    ("شگویا", "پتروشیمی تندگویان", "محصولات شیمیایی", 7.5, 900, 6750, 28, 0.15),
    ("بوعلی", "پتروشیمی بوعلی سینا", "محصولات شیمیایی", 6.2, 1100, 6820, 22, 0.2),
    ("آریا", "پلیمر آریاساسول", "محصولات شیمیایی", 8.0, 2500, 20000, 18, 0.35),
    ("ومعادن", "توسعه معادن و فلزات", "استخراج کانه‌های فلزی", 7.0, 800, 5600, 55, 0.25),
    ("کاما", "باما", "استخراج کانه‌های فلزی", 9.5, 500, 4750, 12, 0.1),
    ("ذوب", "ذوب آهن اصفهان", "فلزات اساسی", 11.0, 200, 2200, 60, 0.05),
    ("ارفع", "آهن و فولاد ارفع", "فلزات اساسی", 8.2, 700, 5740, 20, 0.2),
    ("هرمز", "فولاد هرمزگان جنوب", "فلزات اساسی", 7.8, 650, 5070, 25, 0.22),
    ("تیپیکو", "داروسازی تیپیکو", "مواد و محصولات دارویی", 10.5, 450, 4725, 15, 0.05),
    ("دعبید", "لابراتوارداروسازی دکتر عبیدی", "مواد و محصولات دارویی", 12.0, 380, 4560, 10, 0.0),
    ("برکت", "گروه دارویی برکت", "مواد و محصولات دارویی", 15.0, 200, 3000, 40, -0.1),
    ("حکشتی", "کشتیرانی جمهوری اسلامی", "حمل ونقل آبی", 6.0, 900, 5400, 30, 0.4),
    ("حسینا", "توسعه خدمات دریایی و بندری سینا", "حمل ونقل آبی", 7.5, 400, 3000, 12, 0.2),
    ("اخابر", "مخابرات ایران", "مخابرات", 8.8, 350, 3080, 90, 0.05),
    ("همراه", "ارتباطات سیار ایران", "مخابرات", 7.2, 1200, 8640, 50, 0.1),
    ("رتاپ", "تجارت الکترونیک پارسیان", "رایانه و فعالیت‌های وابسته", 14.0, 250, 3500, 20, 0.3),
    ("پرداخت", "به پرداخت ملت", "رایانه و فعالیت‌های وابسته", 11.5, 400, 4600, 18, 0.25),
    ("اپال", "فرآوری معدنی اپال کانی پارس", "استخراج کانه‌های فلزی", 9.0, 600, 5400, 22, 0.15),
    ("شستان", "سرمایه‌گذاری گروه توسعه ملی", "سرمایه‌گذاریها", 5.8, 700, 4060, 35, 0.1),
    ("وامید", "مدیریت سرمایه امید", "سرمایه‌گذاریها", 6.4, 550, 3520, 28, 0.12),
    ("زاگرس", "پتروشیمی زاگرس", "محصولات شیمیایی", 5.9, 3000, 17700, 15, 0.28),
    ("جم", "پتروشیمی جم", "محصولات شیمیایی", 6.1, 2800, 17080, 20, 0.22),
    ("شکبیر", "پتروشیمی امیرکبیر", "محصولات شیمیایی", 7.0, 1500, 10500, 14, 0.18),
    ("فارس", "صنایع پتروشیمی خلیج فارس", "محصولات شیمیایی", 5.4, 2500, 13500, 100, 0.3),
    ("وپاسار", "بانک پاسارگاد", "بانکها و موسسات اعتباری", 4.5, 600, 2700, 80, 0.08),
    ("ونوین", "بانک اقتصاد نوین", "بانکها و موسسات اعتباری", 5.0, 300, 1500, 45, 0.0),
    ("خگستر", "گسترش سرمایه‌گذاری ایران‌خودرو", "خودرو و ساخت قطعات", 16.0, 90, 1440, 35, 0.4),
    ("ورنا", "ایران‌خودرو دیزل", "خودرو و ساخت قطعات", 13.0, 150, 1950, 25, 0.35),
    ("ثفارس", "عمران و توسعه فارس", "انبوه‌سازی، املاک و مستغلات", 10.0, 200, 2000, 18, 0.15),
    ("ثشاهد", "سرمایه‌گذاری شاهد", "انبوه‌سازی، املاک و مستغلات", 9.5, 180, 1710, 22, 0.1),
    ("سفارس", "سیمان فارس و خوزستان", "سیمان، آهک و گچ", 8.0, 500, 4000, 30, 0.2),
    ("سصوفی", "سیمان صوفیان", "سیمان، آهک و گچ", 7.5, 420, 3150, 12, 0.18),
    ("غپینو", "صنعتی مینو", "محصولات غذایی و آشامیدنی", 11.0, 300, 3300, 15, 0.05),
    ("غگل", "کشت و صنعت گلستان", "محصولات غذایی و آشامیدنی", 12.5, 220, 2750, 10, 0.0),
    ("داسوه", "داروسازی اسوه", "مواد و محصولات دارویی", 13.5, 280, 3780, 8, -0.05),
    ("کحافظ", "کاشی و سرامیک حافظ", "کاشی و سرامیک", 9.0, 150, 1350, 9, 0.1),
    ("لبوتان", "کارخانجات صنعتی بوعلی سینا", "ساخت محصولات فلزی", 10.0, 200, 2000, 7, 0.12),
    ("تفیرو", "توسعه فرابورس ایران", "فعالیتهای کمکی به نهادهای مالی", 20.0, 100, 2000, 50, 0.05),
    ("آسیاتک", "داده‌پردازی آسیاتک", "رایانه و فعالیت‌های وابسته", 18.0, 180, 3240, 14, 0.4),
    ("های‌وب", "داده گستر عصر نوین", "مخابرات", 16.0, 120, 1920, 16, 0.25),
]


def _rng_for(symbol: str, salt: str = "") -> random.Random:
    seed = int(hashlib.md5(f"{symbol}:{salt}:{int(time.time()//30)}".encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def generate_mock_market(n: int | None = None) -> List[SymbolSnapshot]:
    """تولید تابلوی کامل بازار دمو."""
    now = datetime.now(timezone.utc)
    tstr = datetime.now().strftime("%H:%M:%S")
    rows: list[SymbolSnapshot] = []
    symbols = SEED_SYMBOLS if n is None else SEED_SYMBOLS[:n]

    # چند نماد را عمداً «داغ» می‌کنیم تا سیگنال دیده شود
    hot_set = {"خودرو", "فملی", "شپنا", "خساپا", "حکشتی", "آسیاتک", "کگل", "رمپنا"}
    exit_set = {"برکت", "وتجارت", "خپارس", "داسوه"}

    for idx, (l18, l30, cs, pe0, eps0, price0, shares_b, bias) in enumerate(symbols):
        l18 = l18.strip()
        r = _rng_for(l18)
        is_hot = l18 in hot_set or r.random() < 0.08
        is_exit = l18 in exit_set or r.random() < 0.06

        # حرکت قیمت
        base_move = bias * 0.8 + r.uniform(-2.5, 2.5)
        if is_hot and not is_exit:
            # شکار در منفی: plp منفی ولی قدرت خریدار بالا
            if r.random() < 0.55:
                plp = r.uniform(-3.2, -0.3)
            else:
                plp = r.uniform(0.2, 3.8)
        elif is_exit:
            plp = r.uniform(-4.5, -0.5)
        else:
            plp = base_move + r.uniform(-1.2, 1.2)

        plp = _clamp(plp, -4.95, 4.95)
        py = price0 * r.uniform(0.98, 1.02)
        pl = round(py * (1 + plp / 100.0))
        pc = round((pl + py) / 2 * r.uniform(0.995, 1.005))
        pcp = round((pc - py) / py * 100, 2)
        plp = round((pl - py) / py * 100, 2)
        tmax = round(py * 1.05)
        tmin = round(py * 0.95)
        pmax = max(pl, pc, round(py * (1 + abs(plp) / 200)))
        pmin = min(pl, pc, round(py * (1 - abs(plp) / 200)))
        pf = round(py * (1 + r.uniform(-0.01, 0.01)))

        avg_vol = int(shares_b * 1_000_000 * r.uniform(0.002, 0.02))
        if is_hot:
            vol_mult = r.uniform(2.2, 5.5)
        elif is_exit:
            vol_mult = r.uniform(1.8, 3.5)
        else:
            vol_mult = r.uniform(0.4, 1.6)
        tvol = int(avg_vol * vol_mult)
        tval = float(tvol * pl)
        tno = max(50, int(tvol / r.uniform(800, 5000)))

        # حقیقی / حقوقی
        if is_hot and not is_exit:
            buy_i_share = r.uniform(0.62, 0.88)
            sell_i_share = r.uniform(0.35, 0.6)
            buy_count_i = max(20, int(tno * r.uniform(0.15, 0.35)))
            # سرانه بالا = تعداد کمتر خریدار نسبت به حجم
            buy_count_i = max(15, int(buy_count_i * r.uniform(0.35, 0.7)))
            sell_count_i = max(30, int(tno * r.uniform(0.25, 0.55)))
        elif is_exit:
            buy_i_share = r.uniform(0.25, 0.5)
            sell_i_share = r.uniform(0.65, 0.9)
            buy_count_i = max(40, int(tno * r.uniform(0.3, 0.5)))
            sell_count_i = max(15, int(tno * r.uniform(0.1, 0.25)))
        else:
            buy_i_share = r.uniform(0.4, 0.7)
            sell_i_share = r.uniform(0.4, 0.7)
            buy_count_i = max(20, int(tno * r.uniform(0.2, 0.45)))
            sell_count_i = max(20, int(tno * r.uniform(0.2, 0.45)))

        buy_i_vol = tvol * buy_i_share
        buy_n_vol = tvol - buy_i_vol
        sell_i_vol = tvol * sell_i_share
        sell_n_vol = tvol - sell_i_vol
        buy_count_n = max(1, int(buy_count_i * r.uniform(0.02, 0.12)))
        sell_count_n = max(1, int(sell_count_i * r.uniform(0.02, 0.12)))

        # صف تقریبی
        near_ceil = pl >= tmax * 0.985 or plp > 4.5
        near_floor = pl <= tmin * 1.015 or plp < -4.5
        if near_ceil:
            qd1 = tvol * r.uniform(0.5, 2.0)
            qo1 = r.uniform(0, 5000)
            pd1 = tmax
            po1 = tmax
            zd1 = int(r.uniform(50, 400))
            zo1 = max(1, int(r.uniform(1, 5)))
        elif near_floor:
            qd1 = r.uniform(0, 5000)
            qo1 = tvol * r.uniform(0.5, 2.0)
            pd1 = tmin
            po1 = tmin
            zd1 = max(1, int(r.uniform(1, 5)))
            zo1 = int(r.uniform(50, 400))
        else:
            spread = max(1, int(pl * 0.002))
            pd1 = pl - r.randint(0, spread)
            po1 = pl + r.randint(0, spread)
            qd1 = r.uniform(1000, tvol * 0.15)
            qo1 = r.uniform(1000, tvol * 0.15)
            zd1 = int(r.uniform(1, 40))
            zo1 = int(r.uniform(1, 40))

        # برای شکار در منفی نزدیک صف: گاهی تقاضا سنگین در قیمت منفی
        if is_hot and plp < 0 and r.random() < 0.7:
            qd1 = max(qd1, tvol * r.uniform(0.2, 0.8))
            zd1 = max(zd1, int(r.uniform(10, 80)))
            qo1 = min(qo1, tvol * 0.05)
            # فاصله تا سقف هنوز زیاد است ولی تقاضا قوی

        eps = round(eps0 * r.uniform(0.9, 1.1), 1)
        pe = round(pl / eps, 2) if eps else pe0
        mv = pl * shares_b * 1_000_000_000 / 10  # تقریبی

        def depth(level: int, is_buy: bool):
            base_p = pd1 if is_buy else po1
            step = max(1, int(pl * 0.001))
            p = base_p - level * step if is_buy else base_p + level * step
            v = r.uniform(500, tvol * 0.08)
            c = int(r.uniform(1, 25))
            return c, v, p

        row = SymbolSnapshot(
            time=tstr,
            l18=l18,
            l30=l30,
            isin=f"IRO1{hashlib.md5(l18.encode()).hexdigest()[:8].upper()}",
            id=str(10_000_000_000 + idx),
            cs=cs,
            cs_id=str(10 + (idx % 20)),
            z=shares_b * 1_000_000_000,
            bvol=max(1, int(avg_vol * 0.3)),
            mv=mv,
            eps=eps,
            pe=pe,
            tmin=tmin,
            tmax=tmax,
            pmin=pmin,
            pmax=pmax,
            py=round(py),
            pf=pf,
            pl=pl,
            plc=pl - round(py),
            plp=plp,
            pc=pc,
            pcc=pc - round(py),
            pcp=pcp,
            tno=tno,
            tvol=tvol,
            tval=tval,
            Buy_CountI=buy_count_i,
            Buy_CountN=buy_count_n,
            Sell_CountI=sell_count_i,
            Sell_CountN=sell_count_n,
            Buy_I_Volume=buy_i_vol,
            Buy_N_Volume=buy_n_vol,
            Sell_I_Volume=sell_i_vol,
            Sell_N_Volume=sell_n_vol,
            zd1=zd1,
            qd1=qd1,
            pd1=pd1,
            zo1=zo1,
            qo1=qo1,
            po1=po1,
            avg_vol_30d=float(avg_vol),
            avg_val_30d=float(avg_vol * py),
            source="mock",
            updated_at=now,
        )

        # عمق ۲ تا ۵
        for lvl, attr_c, attr_v, attr_p in [
            (2, "zd2", "qd2", "pd2"),
            (3, "zd3", "qd3", "pd3"),
            (4, "zd4", "qd4", "pd4"),
            (5, "zd5", "qd5", "pd5"),
        ]:
            c, v, p = depth(lvl, True)
            setattr(row, attr_c, c)
            setattr(row, attr_v, v)
            setattr(row, attr_p, p)
        for lvl, attr_c, attr_v, attr_p in [
            (2, "zo2", "qo2", "po2"),
            (3, "zo3", "qo3", "po3"),
            (4, "zo4", "qo4", "po4"),
            (5, "zo5", "qo5", "po5"),
        ]:
            c, v, p = depth(lvl, False)
            setattr(row, attr_c, c)
            setattr(row, attr_v, v)
            setattr(row, attr_p, p)

        rows.append(row)

    return rows
