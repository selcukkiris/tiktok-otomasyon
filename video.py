import asyncio, datetime, io, os, random, subprocess
import requests, edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

W, H = 1080, 1920
UA = {"User-Agent": "tarihte-bugun-bot/1.0 (github actions)"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SES = "tr-TR-AhmetNeural"


def olay_sec():
    t = datetime.date.today()
    url = f"https://api.wikimedia.org/feed/v1/wikipedia/tr/onthisday/events/{t.month:02d}/{t.day:02d}"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    olaylar = [e for e in r.json()["events"] if 40 < len(e["text"]) < 220]
    resimli = [e for e in olaylar if any("thumbnail" in p for p in e.get("pages", []))]
    e = random.choice(resimli or olaylar)
    adaylar = []
    for p in e.get("pages", []):
        if "originalimage" in p:
            adaylar.append(p["originalimage"]["source"])
        if "thumbnail" in p:
            adaylar.append(p["thumbnail"]["source"])
    return e["year"], e["text"], adaylar


def arka_plan(adaylar):
    for u in adaylar[:3]:
        try:
            r = requests.get(u, headers=UA, timeout=60)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)).convert("RGB")
            bg = ImageOps.fit(im, (W, H)).filter(ImageFilter.GaussianBlur(30))
            bg = ImageEnhance.Brightness(bg).enhance(0.4)
            fg = ImageOps.contain(im, (W - 120, 800))
            bg.paste(fg, ((W - fg.width) // 2, 380))
            return bg
        except Exception as ex:
            print("Gorsel alinamadi:", ex)
    return Image.new("RGB", (W, H), (20, 30, 60))


def sar(draw, metin, font, genislik):
    satirlar, satir = [], ""
    for k in metin.split():
        deneme = (satir + " " + k).strip()
        if draw.textlength(deneme, font=font) <= genislik:
            satir = deneme
        else:
            satirlar.append(satir)
            satir = k
    if satir:
        satirlar.append(satir)
    return satirlar


def sure(yol):
    c = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", yol], capture_output=True, text=True)
    return float(c.stdout.strip())


async def seslendir(metin, yol):
    await edge_tts.Communicate(metin, SES).save(yol)


def main():
    yil, metin, adaylar = olay_sec()
    anlatim = f"Tarihte bugün. {yil} yılında. {metin}"
    os.makedirs("tmp", exist_ok=True)
    os.makedirs("videolar", exist_ok=True)

    asyncio.run(seslendir(anlatim, "tmp/ses.mp3"))
    toplam = sure("tmp/ses.mp3")

    bg = arka_plan(adaylar)
    d = ImageDraw.Draw(bg)
    f_baslik = ImageFont.truetype(FONT, 80)
    f_yil = ImageFont.truetype(FONT, 150)
    f_alt = ImageFont.truetype(FONT, 66)
    d.text((W // 2, 140), "TARİHTE BUGÜN", font=f_baslik, fill="white",
           anchor="mm", stroke_width=4, stroke_fill="black")
    d.text((W // 2, 280), str(yil), font=f_yil, fill=(255, 210, 60),
           anchor="mm", stroke_width=5, stroke_fill="black")

    kelimeler = anlatim.split()
    parcalar = [" ".join(kelimeler[i:i + 5]) for i in range(0, len(kelimeler), 5)]
    agirlik = sum(len(p) for p in parcalar)

    liste = []
    for i, p in enumerate(parcalar):
        kare = bg.copy()
        dk = ImageDraw.Draw(kare)
        satirlar = sar(dk, p, f_alt, W - 160)
        y = 1350
        for s in satirlar:
            dk.text((W // 2, y), s, font=f_alt, fill="white", anchor="mm",
                    stroke_width=5, stroke_fill="black")
            y += 90
        yol = os.path.abspath(f"tmp/k{i}.png")
        kare.save(yol)
        liste.append((yol, toplam * len(p) / agirlik))

    with open("tmp/liste.txt", "w") as f:
        for yol, sn in liste:
            f.write(f"file '{yol}'\nduration {sn:.3f}\n")
        f.write(f"file '{liste[-1][0]}'\n")

    bugun = datetime.date.today().isoformat()
    cikti = f"videolar/{bugun}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "tmp/liste.txt",
         "-i", "tmp/ses.mp3", "-vf", "format=yuv420p", "-r", "30",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", cikti], check=True)

    with open(f"videolar/{bugun}.txt", "w") as f:
        f.write(f"Tarihte bugün: {yil}\n\n{metin}\n\n"
                "#tarihtebugün #tarih #bilgi #öğrenmeyolu #keşfet\n"
                "Kaynak: Vikipedi")
    print("Hazir:", cikti)


main()
