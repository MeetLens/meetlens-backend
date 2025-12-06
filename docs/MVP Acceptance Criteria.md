# MVP Acceptance Criteria

MVP **başarılı sayılacak** koşullar:

- [ ]  Kullanıcı app’i açıyor → “Start Meeting”e basıyor.
- [ ]  Telefon masada dururken konuşmalar:
    - [ ]  Ekranda **canlı transkript** olarak akıyor.
    - [ ]  Aynı anda **canlı çeviri** görülebiliyor.
- [ ]  “End Meeting”e basınca:
    - [ ]  Toplantının **tam metin transkripti** gösteriliyor.
    - [ ]  GPT ile üretilmiş **özet + action items** gösteriliyor.
- [ ]  Uygulama 30–60 dakikalık bir toplantıyı **crash olmadan** taşıyabiliyor.

Gerisi MVP dışı (pricing, paketler, login vs).

---

## 📱 FRONTEND (Flutter) – MVP Checklist

### 1. Uygulama İskeleti & Ekranlar

- [ ]  **Ana ekran**:
    - [ ]  App bar + basit branding (isim/ikon)
    - [ ]  “Start Meeting” butonu
    - [ ]  Mic permission state’i gösterimi (izin verildi / verilmedi)
- [ ]  **Meeting ekranı**:
    - [ ]  “Listening…” state
    - [ ]  Live **transcript** alanı
    - [ ]  Live **translation** alanı
    - [ ]  “End Meeting” butonu
- [ ]  **Summary ekranı**:
    - [ ]  Toplam transcript (scrollable text)
    - [ ]  Özet (summary)
    - [ ]  Action items bullet listesi
    - [ ]  “Back to Home” butonu

---

### 2. Ses Kaydı (Mic Capture)

- [ ]  `record` ya da `flutter_sound` ile mikrofon kaydı
- [ ]  16 kHz mono PCM formatına ayarlama
- [ ]  **2 saniyelik chunk’lara** bölme (Timer/Stream)
- [ ]  Chunk → `Uint8List` → Base64 encode
- [ ]  Mic izin reddi durumunda:
    - [ ]  Kullanıcıya uyarı
    - [ ]  Ayarlara yönlendirme (opsiyonel)

---

### 3. WebSocket Client

- [ ]  WebSocket servis sınıfı (ör: `MeetingSocketService`)
- [ ]  `connect(sessionId)` fonksiyonu
- [ ]  `sendAudioChunk(sessionId, chunkId, base64)` fonksiyonu
- [ ]  `sendEndSession(sessionId)` fonksiyonu
- [ ]  Connection state yönetimi:
    - [ ]  Connecting / Connected / Error state’leri
- [ ]  Mesajları JSON parse ederek type’a göre dispatch:
    - [ ]  `transcript_partial`
    - [ ]  `transcript_stable`
    - [ ]  `translation`
    - [ ]  `error`

---

### 4. State Management (Transcript & Translation)

- [ ]  Meeting için `MeetingState` modeli:
    - [ ]  `sessionId`
    - [ ]  `unstableTranscript` (ekranda “şu an yazılan” text)
    - [ ]  `stableTranscript` (birikmiş güvenilir text)
    - [ ]  `translation` (hedef dilde birikmiş çeviri)
- [ ]  `transcript_partial` geldiğinde:
    - [ ]  `unstableTranscript` güncellensin
- [ ]  `transcript_stable` geldiğinde:
    - [ ]  `stableTranscript` append edilsin
    - [ ]  `unstableTranscript` reset / temizlenecek kısım silinsin
- [ ]  `translation` geldiğinde:
    - [ ]  `translation` text’e append

---

### 5. Summary Call & UI

- [ ]  “End Meeting”e basınca:
    - [ ]  WebSocket’e `end_session` mesajı gönder
    - [ ]  Local’deki `stableTranscript` string’ini al
    - [ ]  REST `/summary` endpoint’ine POST et
- [ ]  Summary response modeli:
    - [ ]  `short_overview: String`
    - [ ]  `action_items: List<String>`
    - [ ]  `decisions: List<String>`
- [ ]  Summary ekranında:
    - [ ]  Overview bir paragraf
    - [ ]  Action items bullet list
    - [ ]  Decisions bullet list

---

### 6. Temel Hata Yönetimi (Frontend)

- [ ]  WebSocket koparsa:
    - [ ]  Snackbar / banner: “Bağlantı koptu, yeniden deneyin”
- [ ]  Summary endpoint error:
    - [ ]  “Özet oluşturulamadı, sadece transkripti gösteriyorum” fallback’i
- [ ]  UI’da min. loading state’leri:
    - [ ]  “Generating summary…”

---

## 🧱 BACKEND (FastAPI) – MVP Checklist

### 1. Project Setup

- [ ]  FastAPI app iskeleti (`main.py`)
- [ ]  `requirements.txt` / `pyproject.toml` (FastAPI, websockets, httpx/openai vs.)
- [ ]  Basit `uvicorn` run komutu / script

---

### 2. Mesaj Modelleri (Pydantic)

- [ ]  `AudioChunkMessage`:
    
    ```python
    class AudioChunkMessage(BaseModel):
        type: Literal["audio_chunk"]
        session_id: str
        chunk_id: int
        audio_format: Literal["pcm_s16le_16k_mono"]
        data: str
    
    ```
    
- [ ]  `EndSessionMessage`:
    
    ```python
    class EndSessionMessage(BaseModel):
        type: Literal["end_session"]
        session_id: str
    
    ```
    
- [ ]  `TranscriptPartialMessage`, `TranscriptStableMessage`, `TranslationMessage`, `ErrorMessage` modelleri

---

### 3. WebSocket Endpoint `/ws/transcribe`

- [ ]  WS endpoint create
- [ ]  `while True` loop’unda:
    - [ ]  Mesaj al → JSON parse → `type` field’ine göre route et
- [ ]  `audio_chunk` geldiğinde:
    - [ ]  Base64 decode → bytes
    - [ ]  PCM → Whisper’a uygun forma çevir
    - [ ]  Background task olarak işleyebilirsin (opsiyonel)
    - [ ]  Whisper’dan text al
    - [ ]  TranscriptMerger’a ver
    - [ ]  `transcript_partial` ve gerekiyorsa `transcript_stable` mesajı gönder
- [ ]  `end_session` geldiğinde:
    - [ ]  Session state finalize et
    - [ ]  Bu session’ın full transcript’ini RAM’de tut (summary için opsiyonel)

---

### 4. Whisper Entegrasyonu

- [ ]  OpenAI Speech-to-Text API çağrısı:
    - [ ]  Audio chunk gönder
    - [ ]  Transkript text al
- [ ]  Latency ölçümü (log)
- [ ]  Hata durumunda:
    - [ ]  `error` WS mesajı gönder

*(Başlangıç için chunk başına tek call bile yeter; sonra optimize edersin.)*

---

### 5. TranscriptMerger (Stable Transcript Engine)

- [ ]  Session başına state objesi:
    
    ```python
    class SessionState:
        last_stable_text: str
        tail_words: List[str]  # son N kelime
        buffer_unstable: str
        full_transcript: str
    
    ```
    
- [ ]  Her yeni Whisper output için:
    - [ ]  `raw_text` al
    - [ ]  Tail overlap kontrolü (kelime bazında)
    - [ ]  Duplicate kısmı at
    - [ ]  Yeni kelimeleri ekle
- [ ]  Cümle sonu tespiti:
    - [ ]  `.` `?` `!` benzeri işaretlere göre
    - [ ]  Cümle tamamlandığında:
        - [ ]  `transcript_stable` WS mesajı gönder
        - [ ]  `stable_text` + `full_transcript` güncelle
- [ ]  Gerekiyorsa sadece debug için `transcript_partial` da gönder

---

### 6. Translation Pipeline (GPT mini / benzeri)

- [ ]  Stable cümle oluştuğunda:
    - [ ]  O cümleyi translation servis fonksiyonuna ver
    - [ ]  GPT mini’ye kısa prompt ile çeviri iste:
        - Input: `source_sentence`, `source_lang`, `target_lang`
    - [ ]  Çeviri hazır olunca:
        - [ ]  `translation` WS mesajı gönder (`text` = çeviri)
- [ ]  Hata durumunda:
    - [ ]  Log
    - [ ]  WS error mesajı opsiyonel

---

### 7. Summary Endpoint `/summary`

- [ ]  POST `/summary`:
    - [ ]  Body: `session_id`, `full_transcript`, `language`
- [ ]  GPT summary prompt:
    - [ ]  Short overview (3–5 cümle)
    - [ ]  Action items list
    - [ ]  Decisions list
- [ ]  Output modeli:
    
    ```python
    class SummaryResponse(BaseModel):
        summary: SummaryBlock
    
    class SummaryBlock(BaseModel):
        short_overview: str
        action_items: List[str]
        decisions: List[str]
    
    ```
    
- [ ]  Error handling:
    - [ ]  500 → “Summary failed” mesajı

---

### 8. Logging & Basit Monitoring

- [ ]  Her chunk için:
    - [ ]  Whisper latency log
- [ ]  Her session için:
    - [ ]  Toplam süre
    - [ ]  Toplam token / approximate length (opsiyonel)
- [ ]  Basit console log ile başla (MVP için yeterli)

---

## 🚫 MVP DIŞINDA (ŞİMDİLİK YAPMA)

Şimdilik **bilinçli olarak yapmadıkların** (scope creep’i engellemek için):

- [ ]  Kullanıcı kayıt / login / hesap sistemi
- [ ]  Paketler, dakika limiti, pricing
- [ ]  Arşiv listesi (eski toplantıları görme)
- [ ]  Export (PDF, DOCX vs.)
- [ ]  Multi-speaker diarization (kim konuştu?)
- [ ]  Platform-specific entegrasyonlar (Zoom botu, Meet botu vs.)
- [ ]  Offline Whisper (on-device)
- [ ]  iOS’ta system audio direct capture (şimdilik hoparlör + mic)

---

Eğer istersen bir sonraki adımda:

- Bu checklist’ten yola çıkıp **dosya/klasör yapısı** çıkarabiliriz (Flutter + FastAPI).
- Ya da sadece **TranscriptMerger için ayrıntılı pseudocode / Python iskeleti** yazabilirim, sen vibe coding’de direkt üzerinde oynarsın.