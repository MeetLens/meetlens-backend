# API & Schema Contract

This document defines the **canonical contract** between the MeetLens mobile app (Flutter) and the backend (FastAPI). It is the single source of truth for:

- WebSocket protocol
- HTTP endpoints
- Request/response schemas
- Example payloads

All changes to the API **MUST** be reflected here.

---

## 1. Versioning & Conventions

- **API version:** `v0` (MVP)
- **Transport:**
    - WebSocket: JSON messages, UTF-8
    - HTTP: JSON over HTTPS
- **Time:**
    - MVP’de timestamp zorunlu değil; ileride ISO-8601 UTC (`2025-12-04T13:37:00Z`) kullanılacak.
- **IDs:**
    - `session_id`: UUID v4 string (client-generated is OK in MVP)
    - `chunk_id`: incremental integer per session, starting at 1

---

## 2. WebSocket API – `/ws/transcribe`

**URL (MVP):**

- `wss://<backend-host>/ws/transcribe`

Bidirectional WebSocket kanalında aşağıdaki tipte JSON mesajlar taşınır.

### 2.1. Common Envelope

Her mesajda şu alanlar olmalıdır:

```json
{
  "type": "string",        // message type discriminator
  "session_id": "string"   // logical meeting session id
}
``

### 2.2. Client → Server Message Types

#### 2.2.1. `audio_chunk`

Kullanıcı cihazından gelen ham ses verisi.

**Type:** `audio_chunk`

```jsonc
{
  "type": "audio_chunk",
  "session_id": "d9f3d2c4-4c60-4d51-9b7f-1f7d0c07b111",
  "chunk_id": 1,
  "audio_format": "pcm_s16le_16k_mono",  // sabit MVP formatı
  "data": "BASE64_ENCODED_AUDIO_BYTES"
}

```

- `chunk_id`: 1, 2, 3, …
- `audio_format`: MVP’de sabit; ileride enum genişletilebilir.

**Backend behavior (MVP):**

- Base64 decode → bytes
- PCM → Whisper-compatible input
- Whisper’dan transcription al
- TranscriptMerger’a ilet
- `transcript_partial` ve gerektiğinde `transcript_stable` mesajlarıyla client’a geri dön.

---

### 2.2.2. `end_session`

Kullanıcı toplantıyı bitirdiğinde gönderilir.

**Type:** `end_session`

```json
{
  "type": "end_session",
  "session_id": "d9f3d2c4-4c60-4d51-9b7f-1f7d0c07b111"
}

```

**Backend behavior (MVP):**

- Bu session için artık `audio_chunk` kabul edilmez (görmezden gelinebilir veya error dönebilir).
- Session state finalize edilir (TranscriptMerger full transcript hazır durumda tutulur).
- Full transcript daha sonra `/summary` endpoint’ine verilmek üzere RAM’de veya geçici storagede tutulabilir.

---

### 2.3. Server → Client Message Types

### 2.3.1. `transcript_partial`

Whisper + merger pipeline’dan çıkan **anlık / unstable** transcript.

**Type:** `transcript_partial`

```json
{
  "type": "transcript_partial",
  "session_id": "d9f3d2c4-4c60-4d51-9b7f-1f7d0c07b111",
  "chunk_id": 1,
  "text": "Benim ad"
}
```

- `text`: Şu an işlenen chunk’a karşılık gelen geçici transkript (tam cümle olmak zorunda değil).
- `chunk_id`: Bu partial’ın ait olduğu chunk/segment. Aynı `chunk_id` ile gelen stable event partial’ı **değiştirir**; frontend partial bloğunu bu kimlikle güncellemelidir.
- Client tarafında bu metin **gri / italik** gibi unstable olarak gösterilebilir.

---
### 2.3.2. `transcript_stable`

Merger tarafından **güvenli, tamamlanmış** olduğu düşünülen transcript parçaları.

**Type:** `transcript_stable`

```json
{
  "type": "transcript_stable",
  "session_id": "d9f3d2c4-4c60-4d51-9b7f-1f7d0c07b111",
  "chunk_id": 1,
  "text": "Benim adım Kadir."
}
```

- `text`: Full transcriptin **sona eklenecek** kısmı.
- `chunk_id`: Stable segment kimliği; aynı `chunk_id` ile gelen yeni stable mesajı önceki stable/partial bloğunu **overwrite** eder (ElevenLabs önceki segmentleri revize edebilir).
- Client tarafında:
    - `stableTranscript[chunk_id] = text` (veya aynı etkiyi yaratacak replace işlemi)
    - `unstableTranscript` içindeki ilgili kısım temizlenebilir.

**Not:** `transcript_stable` mesajları incremental olarak gelir; client tam transcript’i, gelen `chunk_id` sırasına göre append ederek veya map üzerinden sıralayarak oluşturur.

---
### 2.3.3. `translation`

Stable bir cümle veya segment için üretilmiş çeviri.

**Type:** `translation`

```json
{
  "type": "translation",
  "session_id": "d9f3d2c4-4c60-4d51-9b7f-1f7d0c07b111",
  "chunk_id": 1,
  "text": "My name is Kadir."
}
```

- `text`: Hedef dilde (MVP’de sabit: örn. English → Turkish veya tersi) çeviri.
- `chunk_id`: Çevirinin ait olduğu transkript segmenti. Aynı `chunk_id` ile gelen yeni çeviri önceki bloğun **yerine** geçer (stable revizyonlarında overwrite). Client append etmek yerine `translationBlocks[chunk_id] = text` şeklinde güncellemeli.

**MVP simplifying assumption:**

- Her `transcript_stable` segmenti için **en az bir** `translation` mesajı gelir.
- Çeviri, segment bazlı olduğu için baştan sona gelen tek bir string olarak birikmesi yeterlidir (chunk_id sıralı append veya map üzerinde join yeterli).

---
### 2.3.4. `error`

İşlenemeyen chunk, model hatası vb. durumlarda backend’in gönderdiği hata mesajı.

**Type:** `error`

```json
{
  "type": "error",
  "session_id": "d9f3d2c4-4c60-4d51-9b7f-1f7d0c07b111",
  "message": "Whisper failed for chunk 42.",
  "code": "WHISPER_ERROR"  // optional
}

```

- `message`: İnsan tarafından okunabilir kısa açıklama
- `code`: İleride programatik handling için enum benzeri string (MVP için opsiyonel)

**Client behavior (MVP):**

- Snackbar / toast ile kullanıcıya göster
- Debug log’a yaz
- Akışı durdurmak zorunda değilsin; hata chunk bazlı olabilir.

---

## 3. HTTP API

MVP’de tek zorunlu endpoint: **summary**.

### 3.1. `POST /summary`

Toplantı bittikten sonra full transcript üzerinden özet üreten endpoint.

**URL:**

- `POST https://<backend-host>/summary`

**Request Body:**

```json
{
  "session_id": "d9f3d2c4-4c60-4d51-9b7f-1f7d0c07b111",
  "full_transcript": "Benim adım Kadir. Bugün proje hakkında konuştuk...",
  "language": "tr"  // source transcript language (best-effort)
}

```

- `session_id`: WS için kullanılan session id ile aynı
- `full_transcript`: Client’ın elindeki tamamen birleştirilmiş transcript
    - MVP: Client gönderebilir (tek kaynak client)
    - Gelecekte: Backend de kendi kayıt ettiği transcript’i kullanabilir
- `language`: Kaynak dil (ör. `"en"`, `"tr"`, `"de"`). MVP’de optional, ama varsa prompt’ta kullanılabilir.

**Response 200 OK:**

```json
{
  "summary": {
    "short_overview": "Toplantıda yeni ürün fikri tartışıldı ve MVP kapsamı netleştirildi.",
    "action_items": [
      "Aşkın MVP için backend iskeletini kuracak.",
      "Ses chunk streaming implementasyonu test edilecek.",
      "Sonraki toplantıda fiyatlandırma stratejisi gözden geçirilecek."
    ],
    "decisions": [
      "Ürün adı MeetLens olarak belirlendi.",
      "İlk sürümde sadece tek dil çifti desteklenecek."
    ]
  }
}

```

**Error Responses (MVP suggestion):**

- `400 Bad Request` – body eksik / json parse edilemedi
    
    ```json
    {
      "detail": "full_transcript is required"
    }
    
    ```
    
- `500 Internal Server Error` – OpenAI / model hatası vb.
    
    ```json
    {
      "detail": "Failed to generate summary"
    }
    
    ```
    

---

## 4. Data Models (Backend Internal)

Bu bölüm backend içindeki sınıflar için referans; frontend bunları **bilmek zorunda değil**, ama kontratın mantığını anlamaya yardımcı olur.

### 4.1. `SessionState`

```python
from pydantic import BaseModel
from typing import Dict, List

class SessionState(BaseModel):
    session_id: str
    last_stable_text: str = ""
    tail_words: List[str] = []      # overlap için son N kelime
    buffer_unstable: str = ""      # son chunk’tan gelen unstable parça
    full_transcript: str = ""      # tüm stable transcript
    stable_segments: Dict[int, str] = {}  # committed transcript segmentleri (chunk_id → text)

```

### 4.2. WebSocket Message Models (Pydantic)

```python
from typing import Literal, Optional
from pydantic import BaseModel

class AudioChunkMessage(BaseModel):
    type: Literal["audio_chunk"]
    session_id: str
    chunk_id: int
    audio_format: Literal["pcm_s16le_16k_mono"]
    data: str  # base64

class EndSessionMessage(BaseModel):
    type: Literal["end_session"]
    session_id: str

class TranscriptPartialMessage(BaseModel):
    type: Literal["transcript_partial"]
    session_id: str
    chunk_id: int
    text: str

class TranscriptStableMessage(BaseModel):
    type: Literal["transcript_stable"]
    session_id: str
    chunk_id: int
    text: str

class TranslationMessage(BaseModel):
    type: Literal["translation"]
    session_id: str
    chunk_id: int
    text: str

class ErrorMessage(BaseModel):
    type: Literal["error"]
    session_id: str
    message: str
    code: Optional[str] = None

```

### 4.3. Summary Models

```python
from pydantic import BaseModel
from typing import List

class SummaryBlock(BaseModel):
    short_overview: str
    action_items: List[str]
    decisions: List[str]

class SummaryRequest(BaseModel):
    session_id: str
    full_transcript: str
    language: str | None = None

class SummaryResponse(BaseModel):
    summary: SummaryBlock

```

---

## 5. Example Flows

### 5.1. Normal Meeting Flow (Happy Path)

1. **Client:** Generate `session_id` (UUID v4).
2. **Client:** WebSocket’e bağlan: `/ws/transcribe`.
3. **Client:** Her 2 saniyede bir `audio_chunk` mesajı gönder.
4. **Server:** Her chunk için:
    - Whisper → transcript
    - Merger → `transcript_partial` + gerektiğinde `transcript_stable`
    - Çeviri → `translation`
5. **Client:**
    - `transcript_partial` → UI’da unstable text
    - `transcript_stable` → stable transcript’e append
    - `translation` → translation text’e append
6. **Client:** Kullanıcı "End Meeting"e basar → `end_session` mesajı gönder.
7. **Client:** Toplanan `stableTranscript` string’ini `/summary` endpoint’ine POST eder.
8. **Server:** GPT ile summary üretir → `SummaryResponse` döner.
9. **Client:** Summary ekranında full transcript + summary gösterir.

---

## 6. Non-Goals & Simplifications (MVP)

- **Authentication yok:**
    - Tüm istekler anonymous kabul edilir.
- **Rate limiting yok:**
    - MVP’de limit yok; ileride eklenebilir.
- **Çoklu dil desteği sınırlı:**
    - MVP’de tek ana dil çifti (ör. EN → TR) üstüne optimize edilir.
- **Diarization yok:**
    - Kim konuştu bilgisi yok, sadece düz transcript.
- **Partial summary yok:**
    - Özet sadece toplantı sonunda üretilir.

---

## 7. Change Log (MVP Phase)

- **v0.1** – Initial contract
    - WebSocket: `audio_chunk`, `end_session`, `transcript_partial`, `transcript_stable`, `translation`, `error`
    - HTTP: `POST /summary`
    - Internal models: `SessionState`, Summary models