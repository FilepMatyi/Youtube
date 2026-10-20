# ShortForge — jelenleg elérhető használat

1. Telepíts Python 3.10/3.11-et és FFmpeg/ffprobe-ot; kövesd a `README.md` telepítési lépéseit.
2. Indítsd a helyi Streamlit felületet, majd válassz YouTube-linket vagy saját MP4/MOV/MKV videót (feltöltéssel vagy helyi fájlútvonallal).
3. Válassz 4–6 highlightot, egy 15–180 mp közötti célhosszprofilt és beszélt nyelvet. Az eredeti nyelvű felirat alapértelmezett; az angol fordítás külön sáv.
4. Rögzítsd a forrás jogalapját, jogosultját/licencét/engedélyét, és erősítsd meg a felhasználási jogot.
5. Indítsd a feldolgozást; a kész klipeket az oldalon nézheted meg és egyenként töltheted le. A fájlok az `output/<job-id>/` könyvtárban maradnak.

Az Original Content munkafolyamatban a forrás importja után témát választhatsz. Ha a helyi Ollama fut és van telepített modell, készíthetsz bizonyítékokhoz kötött forgatókönyv-javaslatot, amelyet átírhatsz és verziózott JSON-ként menthetsz. A hivatkozás szerkezeti ellenőrzése nem bizonyítja az állítás igazságát: a forrásértelmezés és a külső tények emberi ellenőrzést igényelnek.

Az angolra fordított felirat csak mondatszintű időzítést kap jelenleg. Original narráció/videóexport, részletes szerkesztő, háttérjob és több crop mód még fejlesztés alatt van; az alkalmazás ezeket nem kínálja kész funkcióként. Nem történik automatikus publikálás.
