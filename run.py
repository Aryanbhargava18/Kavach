"""Start Kavach on this laptop and print where each product opens, for this screen and for phones on the same Wi-Fi.

    python run.py            (after: pip install -r requirements.txt)
Works on macOS, Windows and Linux; `make lan` does the same with a virtualenv.
"""
import os
import socket


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))       # no packet is sent; this just picks the Wi-Fi interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    ip, port = lan_ip(), int(os.environ.get("PORT", "8000"))
    os.environ.setdefault("KAVACH_PUBLIC_URL", f"http://{ip}:{port}")
    base = os.environ["KAVACH_PUBLIC_URL"]
    print(f"""
  Kavach is starting.

  On this laptop (projector)     http://localhost:{port}/          all three side by side
  Meena's app (judge's phone)    {base}/m
  Her Soundbox (spare phone)     {base}/soundbox     tap once to switch on sound
  Paytm's staff website          {base}/desk         and {base}/ops
  The world (simulator)          {base}/world        a teammate plays customer, bank and police
  One case, end to end           {base}/case

  Phones must be on the same Wi-Fi (or the laptop's hotspot). Drive it from /world (or keys 1, 2, 3, right arrow, R on the main screen).
""")
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="warning")
