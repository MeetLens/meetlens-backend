# MVP Acceptance Criteria

MVP **başarılı sayılacak** koşullar:

- [ ]  Kullanıcı app'i açıyor → "Start Meeting"e basıyor.
- [ ]  Telefon masada dururken konuşmalar:
    - [ ]  Ekranda **canlı transkript** olarak akıyor.
    - [ ]  Aynı anda **canlı çeviri** görülebiliyor.
- [ ]  "End Meeting"e basınca:
    - [ ]  Toplantının **tam metin transkripti** gösteriliyor.
    - [ ]  GPT ile üretilmiş **özet + action items** gösteriliyor.
- [ ]  Uygulama 30–60 dakikalık bir toplantıyı **crash olmadan** taşıyabiliyor.

Gerisi MVP dışı (pricing, paketler, login vs).

---

## 📱 FRONTEND (Flutter Mobile & Electron Desktop) – MVP Checklist

### 1. Uygulama İskeleti & Ekranlar

- [ ]  **Ana ekran**:
    - [ ]  App bar + basit branding (isim/ikon)
    - [ ]  "Start Meeting" butonu
    - [ ]  Mic permission state'i gösterimi (izin verildi / verilmedi)
- [ ]  **Meeting ekranı**:
    - [ ]  "Listening…" state
    - [ ]  Live **transcript** alanı
    - [ ]  Live **translation** alanı
    - [ ]  "End Meeting" butonu
- [ ]  **Summary ekranı**:
    - [ ]  Toplam transcript (scrollable text)
    - [ ]  Özet (summary)
    - [ ]  Action items bullet listesi
    - [ ]  "Back to Home" butonu

---

### 2. Ses Kaydı (Mic Capture)

- [ ]  `record` ya da `flutter_sound` ile mikrofon kaydı
- [ ]  16 kHz mono PCM formatına ayarlama
- [ ]  **2 saniyelik chunk'lara** bölme (Timer/Stream)
- [ ]  Chunk → `Uint8List` → Base64 encode
- [ ]  Mic izin reddi durumunda:
    - [ ]  Kullanıcıya uyarı
    - [ ]  Ayarlara yönlendirme (opsiyonel)

---

### 3. WebSocket Client

- [ ]  WebSocket servis sınıfı (ör: `MeetingSocketService`)
- [ ]  `connect(sessionId)` fonksiyonu
- [ ]  `sendAudioChunk(sessionId, chunkId, base64)` fonksiyonu
- [ ]  `sendEndSession(sessionId)` fonksiyonu
- [ ]  Connection state yönetimi:
    - [ ]  Connecting / Connected / Error state'leri
- [ ]  Mesajları JSON parse ederek type'a göre dispatch:
    - [ ]  `transcript_partial`
    - [ ]  `transcript_stable`
    - [ ]  `translation_partial`
    - [ ]  `translation_stable`
    - [ ]  `error`

---

### 4. State Management (Transcript & Translation)

- [ ]  Meeting için `MeetingState` modeli:
    - [ ]  `sessionId`
    - [ ]  `unstableTranscript` (ekranda "şu an yazılan" text)
    - [ ]  `stableTranscript` (birikmiş güvenilir text)
    - [ ]  `unstableTranslation` (preview translation)
    - [ ]  `stableTranslation` (hedef dilde birikmiş çeviri)
- [ ]  `transcript_partial` geldiğinde:
    - [ ]  `unstableTranscript` güncellensin
- [ ]  `transcript_stable` geldiğinde:
    - [ ]  `stableTranscript` append edilsin
    - [ ]  `unstableTranscript` reset / temizlenecek kısım silinsin
- [ ]  `translation_partial` geldiğinde:
    - [ ]  `unstableTranslation` overwrite edilsin (preview)
- [ ]  `translation_stable` geldiğinde:
    - [ ]  `stableTranslation` append edilsin
    - [ ]  `unstableTranslation` temizlensin

---

### 5. Summary Call & UI

- [ ]  "End Meeting"e basınca:
    - [ ]  WebSocket'e `end_session` mesajı gönder
    - [ ]  Local'deki `stableTranscript` string'ini al
    - [ ]  REST `/summary` endpoint'ine POST et
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
    - [ ]  Snackbar / banner: "Bağlantı koptu, yeniden deneyin"
- [ ]  Summary endpoint error:
    - [ ]  "Özet oluşturulamadı, sadece transkripti gösteriyorum" fallback'i
- [ ]  UI'da min. loading state'leri:
    - [ ]  "Generating summary…"

---

## 🧱 BACKEND (FastAPI) – MVP Checklist

### 1. Project Setup ✅

- [x]  FastAPI app iskeleti (`main.py`)
- [x]  `requirements.txt` (FastAPI, websockets, openai, elevenlabs, etc.)
- [x]  Uvicorn run komutu / Procfile

---

### 2. Mesaj Modelleri (Pydantic) ✅

- [x]  `AudioChunkMessage`
- [x]  `EndSessionMessage`
- [x]  `TranscriptPartialMessage`
- [x]  `TranscriptStableMessage`
- [x]  `TranslationPartialMessage`
- [x]  `TranslationStableMessage`
- [x]  `ErrorMessage`
- [x]  `SummaryRequest`, `SummaryResponse`, `SummaryBlock`

**Location**: [models/messages.py](../../models/messages.py)

---

### 3. WebSocket Endpoint `/ws/transcribe` ✅

- [x]  WS endpoint create
- [x]  `while True` loop'unda mesaj alma ve JSON parse
- [x]  `audio_chunk` handling:
    - [x]  Base64 decode → bytes
    - [x]  Forward to ElevenLabs Scribe v2 Realtime API
    - [x]  Receive partial_transcript and committed_transcript events
    - [x]  Send `transcript_partial` and `transcript_stable` messages
- [x]  `end_session` handling:
    - [x]  Close ElevenLabs session
    - [x]  Finalize session state

**Implementation**: [endpoints/websocket.py](../../endpoints/websocket.py)

**Note**: Uses ElevenLabs instead of Whisper + TranscriptMerger for better latency.

---

### 4. Transcription Service ✅

- [x]  **ElevenLabs Scribe v2 Integration** (Current)
    - [x]  WebSocket connection management
    - [x]  Audio chunk forwarding
    - [x]  Event processing (partial_transcript, committed_transcript)
    - [x]  Error handling
    
- [x]  **OpenAI Whisper Service** (Alternative - Not Used)
    - [x]  PCM to WAV conversion
    - [x]  Whisper API calls
    - [x]  Error handling

**Location**: 
- [services/elevenlabs_service.py](../../services/elevenlabs_service.py) (Active)
- [services/whisper_service.py](../../services/whisper_service.py) (Alternative)

---

### 5. TranscriptMerger ✅ (Not Used in MVP)

- [x]  Session state management
- [x]  Tail overlap detection (word-level deduplication)
- [x]  Sentence boundary detection
- [x]  Stable segment emission

**Location**: [services/transcript_merger.py](../../services/transcript_merger.py)

**Note**: Not used in MVP. ElevenLabs provides built-in transcript merging via `committed_transcript` events.

---

### 6. Translation Pipeline ✅

- [x]  Stable segment translation (OpenAI GPT)
- [x]  Partial translation for live preview
- [x]  Stable translation accumulation
- [x]  Full retranslation when needed (for corrections)
- [x]  Error handling with `translation_error` messages

**Implementation**: [services/translation_service.py](../../services/translation_service.py) + [endpoints/websocket.py](../../endpoints/websocket.py)

---

### 7. Summary Endpoint `/summary` ✅

- [x]  POST `/summary` endpoint
- [x]  Request validation (session_id, full_transcript, language)
- [x]  GPT summary prompt with structured output:
    - [x]  Short overview (2-5 sentences)
    - [x]  Action items list
    - [x]  Decisions list
- [x]  Error handling (400, 500)

**Implementation**: [main.py](../../main.py) + [services/summary_service.py](../../services/summary_service.py)

---

### 8. Session Management ✅

- [x]  In-memory SessionState storage
- [x]  `get_or_create(session_id)` API
- [x]  State tracking (full_transcript, stable_translation, partial_translation)
- [x]  Thread-safe async operations

**Implementation**: [services/session_manager.py](../../services/session_manager.py)

---

### 9. Logging & Monitoring ✅

- [x]  Structured logging with log levels
- [x]  Chunk processing logs
- [x]  API error logging
- [x]  Session lifecycle logging

**Implementation**: Throughout codebase using Python `logging` module

---

## 🚫 MVP DIŞINDA (Phase 2)

Şimdilik **bilinçli olarak yapmadıkların** (scope creep'i engellemek için):

### Backend - Phase 2 Tasks

- [ ]  **Authentication System** (Database schema ready, endpoints not implemented)
    - [ ]  User signup endpoint (`POST /auth/signup`)
    - [ ]  User login endpoint (`POST /auth/login`)
    - [ ]  Magic link authentication (`POST /auth/magic-link`, `POST /auth/magic-link/verify`)
    - [ ]  Password reset flow (`POST /auth/password-reset`, `POST /auth/password-reset/verify`)
    - [ ]  Session middleware (token validation)
    - [ ]  Protected WebSocket and HTTP endpoints
    
- [ ]  **Database Integration** (Schema complete, not integrated)
    - [ ]  Connect FastAPI to PostgreSQL
    - [ ]  Meeting persistence (transcripts, summaries, metadata)
    - [ ]  User account management
    - [ ]  Usage tracking and analytics
    
- [ ]  **Meeting Archive**
    - [ ]  `GET /meetings` - List user's meetings
    - [ ]  `GET /meetings/{id}` - Get meeting details
    - [ ]  `DELETE /meetings/{id}` - Soft delete meeting
    
- [ ]  **Export Functionality**
    - [ ]  PDF export
    - [ ]  DOCX export
    - [ ]  Plain text export
    
- [ ]  **Usage Tracking & Limits**
    - [ ]  Per-user minute quotas
    - [ ]  Pricing tier enforcement
    - [ ]  Usage analytics dashboard
    
- [ ]  **Advanced Features**
    - [ ]  Multi-speaker diarization (who said what)
    - [ ]  Custom vocabulary/glossary
    - [ ]  Multiple language pair support
    - [ ]  Platform integrations (Zoom bot, Meet bot)

### Frontend - Phase 2 Tasks

- [ ]  User authentication flows (signup, login, password reset)
- [ ]  Meeting history/archive list
- [ ]  Export buttons (PDF, DOCX)
- [ ]  Usage dashboard (minutes used, quota remaining)
- [ ]  Account settings page
- [ ]  Offline mode (on-device Whisper for Pro users)
- [ ]  System audio capture (iOS)

---

## 📊 Implementation Status Summary

### Backend MVP: **✅ COMPLETE**

**Implemented:**
- ✅ Real-time transcription (ElevenLabs Scribe v2)
- ✅ Live translation (OpenAI GPT)
- ✅ Meeting summaries (OpenAI GPT)
- ✅ WebSocket streaming
- ✅ Session management
- ✅ Error handling
- ✅ CORS configuration
- ✅ Health check endpoint

**Ready but Not Used:**
- ✅ Database schema (PostgreSQL)
- ✅ Authentication tables and repositories
- ✅ OpenAI Whisper alternative
- ✅ Custom TranscriptMerger

**Not Implemented (Phase 2):**
- ❌ Authentication endpoints
- ❌ Database integration
- ❌ Meeting persistence
- ❌ User management
- ❌ Usage tracking/limits

### Frontend MVP: **⏳ IN PROGRESS**

Check frontend repository for implementation status.

---

## 🔄 Migration Path: Whisper Alternative

If switching from ElevenLabs to Whisper is needed:

1. **Update `endpoints/websocket.py`:**
   ```python
   # Replace ElevenLabs imports with Whisper
   from services.whisper_service import transcribe_audio
   from services.transcript_merger import process_transcript
   ```

2. **Change audio processing flow:**
   - Call `transcribe_audio()` instead of forwarding to ElevenLabs
   - Pass result to `process_transcript()` for merging
   - Use returned `partial_text` and `stable_segment` for messages

3. **Update environment variables:**
   - Remove `ELEVENLABS_API_KEY`
   - Ensure `OPENAI_API_KEY` is set

Both implementations are fully functional and tested.

---

## 📚 Documentation Status

- ✅ [README.md](../../README.md) - Updated with ElevenLabs info
- ✅ [Architecture Flow](../architecture/FLOW.md) - Updated to reflect ElevenLabs usage
- ✅ [API & Schema Contract](../api/CONTRACT.md) - Updated with translation fields
- ✅ [Database Implementation Summary](../database/IMPLEMENTATION_SUMMARY.md) - Marked as Phase 2
- ✅ Code documentation - Inline comments added to alternative implementations

---

**Next Steps**: Frontend implementation and integration testing with backend.
