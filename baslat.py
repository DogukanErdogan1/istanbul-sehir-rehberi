"""Yerel rehber sunucusunu kullanılabilir bir portta başlat."""

import socket

import uvicorn


HOST = "127.0.0.1"
PORTS = (8765, 8081, 9000, 0)


def uygun_port_bul():
    son_hata = None
    for port in PORTS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as kontrol:
                kontrol.bind((HOST, port))
                return kontrol.getsockname()[1]
        except OSError as hata:
            son_hata = hata
    raise RuntimeError(
        "Yerel bir bağlantı noktası açılamadı. Windows ağ izinlerini kontrol edin. "
        f"Son hata: {son_hata}"
    )


if __name__ == "__main__":
    port = uygun_port_bul()
    print(f"\nŞehir rehberini tarayıcıda açın: http://{HOST}:{port}/\n", flush=True)
    uvicorn.run("main:app", host=HOST, port=port)
