# Cấu trúc mã nguồn Chatbot

Tài liệu mô tả cấu trúc hiện có của folder `Chatbot`, cập nhật ngày 03/10/2026. Dự án gồm backend Python/FastAPI, widget JavaScript tích hợp Excalidraw và trang nhập prompt độc lập.

## 1. Cây thư mục

Cây dưới đây tập trung vào mã nguồn và dữ liệu chính; lược bỏ dependency đã cài, file khóa dependency, file môi trường, cache và các file `__init__.py`.

```text
Chatbot/
├── README.md                         # Giới thiệu, cách chạy backend, API chính
├── package.json                      # Dependency JavaScript tại root
├── requirement.doc                   # Chuyển tiếp tới backend/requirements.txt
│
├── prompt_box/                       # Trang nhập prompt ban đầu
│   ├── index.html                    # Form nhập prompt và nút quay lại
│   ├── prompt.css                    # Giao diện trang prompt
│   ├── prompt.js                     # Xử lý submit và sessionStorage
│   └── assets/
│       └── noprompt.png
│
├── widget/                           # Widget chat nhúng vào ứng dụng chủ
│   ├── package.json                  # Marked, DOMPurify, Interact.js
│   └── src/
│       ├── chatbot-widget.js         # Điểm vào, ghép UI và gắn sự kiện chat
│       ├── bootstrap.js              # Helper nạp CSS và chờ DOM sẵn sàng
│       ├── config.js                 # Cấu hình URL cho widget
│       ├── integrations/
│       │   └── excalidraw.js         # Kết nối bridge Excalidraw
│       ├── network/
│       │   └── public-ip.js          # Helper xử lý/xác nhận public IPv4
│       ├── utils/
│       │   └── equation-groups.js    # Gom các nét thành nhóm công thức
│       ├── ui/
│       │   ├── widget.js             # Tạo khung widget
│       │   ├── header.js             # Header widget
│       │   ├── course-badge.js       # Thành phần nhãn khóa học
│       │   ├── toggle-button.js      # Nút mở/đóng widget
│       │   ├── animations.js         # Hiệu ứng giao diện
│       │   ├── interactions.js       # Kéo và thay đổi kích thước
│       │   └── chat/
│       │       ├── input.js          # Ô nhập và nút gửi tin
│       │       └── messages.js       # Gửi API, hiển thị tin nhắn/Markdown
│       └── styles/
│           ├── widget.css
│           ├── header.css
│           ├── chat.css
│           ├── toggle-button.css
│           └── course-badge.css
│
├── backend/
│   ├── run.py                        # Khởi chạy Uvicorn
│   ├── requirements.txt              # Dependency Python
│   ├── app/
│   │   ├── main.py                   # FastAPI, CORS, router, lifecycle
│   │   ├── core/
│   │   │   ├── config.py             # Cấu hình môi trường
│   │   │   ├── paths.py              # Đường dẫn dữ liệu của dự án
│   │   │   └── state_store.py        # Trạng thái và lịch sử trong RAM
│   │   ├── api/
│   │   │   ├── whiteboard.py         # Gợi ý toán và thao tác bảng
│   │   │   └── routes/
│   │   │       ├── chat.py           # Nhận câu hỏi và ngữ cảnh bảng
│   │   │       ├── analyze.py        # API phân tích ảnh/OCR
│   │   │       ├── equations.py      # Gom, OCR và đồng bộ công thức
│   │   │       ├── strokes.py        # Đồng bộ nét vẽ
│   │   │       ├── images.py         # Nhận ảnh bảng
│   │   │       ├── whiteboard_state.py # Lưu/đọc snapshot bảng trên đĩa
│   │   │       ├── state.py          # Đọc trạng thái trong RAM
│   │   │       ├── history.py        # Đọc lịch sử phân tích OCR
│   │   │       ├── presence.py       # Join, heartbeat, leave, trạng thái phòng
│   │   │       ├── client.py         # API địa chỉ IP client
│   │   │       ├── excalidraw_store.py # Proxy lưu/đọc bản chia sẻ
│   │   │       └── health.py         # Kiểm tra sức khỏe backend
│   │   ├── services/
│   │   │   ├── openai_service.py     # Gọi AI trả lời và phân tích ảnh
│   │   │   ├── equation_context.py   # Xây dựng ngữ cảnh công thức
│   │   │   ├── equation_ocr.py       # OCR cho công thức riêng lẻ
│   │   │   ├── stroke_grouper.py     # Gom nét vẽ phía backend
│   │   │   ├── detector.py           # Phát hiện đối tượng bằng Transformers
│   │   │   ├── visual_geometry.py    # Đổi tọa độ bbox ảnh sang Excalidraw
│   │   │   ├── room_presence.py      # Quản lý và dọn phiên presence
│   │   │   ├── whiteboard_action_logger.py # Ghi log thao tác bảng
│   │   │   └── paddle/
│   │   │       ├── model.py          # Khởi tạo/cache PaddleOCR-VL
│   │   │       ├── analyzer.py       # Phân tích ảnh bảng và ảnh công thức
│   │   │       ├── parser.py         # Trích xuất công thức, bbox từ OCR
│   │   │       └── formatter.py      # Định dạng kết quả phân tích
│   │   ├── reasoning/
│   │   │   ├── pipeline.py           # Điều phối pipeline suy luận toán
│   │   │   ├── equation_adapter.py   # Chuyển dữ liệu vào pipeline
│   │   │   ├── equation_parser.py    # Parse phương trình
│   │   │   ├── relationship.py       # Xác định quan hệ giữa phương trình
│   │   │   ├── graph.py              # Xây dựng đồ thị phương trình
│   │   │   ├── frontier.py           # Tìm điểm để tiếp tục giải
│   │   │   ├── next_step.py          # Sinh bước giải tiếp theo
│   │   │   └── instruction.py        # Tạo hướng dẫn cho người học
│   │   ├── schemas/
│   │   │   └── analysis.py           # Schema Pydantic
│   │   └── utils/
│   │       └── images.py             # Tiện ích xử lý ảnh upload
│   ├── data/                         # Ảnh/cache phân tích hiện có ở backend
│   │   ├── whiteboard_images/
│   │   └── whiteboard_image_analysis/
│   └── logs/
│       └── openai_requests.jsonl     # Log request AI hiện có
│
├── data/                             # Dữ liệu bảng tại root
│   ├── strokes.json                  # Snapshot nét vẽ
│   ├── equations.json                # Công thức đã gom/nhận dạng
│   ├── whiteboard_state.json         # File snapshot hiện có
│   ├── whiteboard_actions.jsonl      # Log thao tác bảng
│   ├── grounding_dino_test.jpg       # Ảnh phục vụ thử detector
│   ├── whiteboard_images/            # Ảnh bảng được lưu
│   └── whiteboard_state/
│       ├── elements.json             # Các phần tử Excalidraw
│       └── app_state.json            # Trạng thái giao diện bảng
│
├── docs/
│   ├── CODE_STRUCTURE.md             # Tài liệu này
│   ├── chatbot-code-structure.html   # Báo cáo HTML đã có
│   ├── chatbot-code-structure.pdf    # Báo cáo PDF đã có
│   └── agent-architecture.pdf        # Tài liệu kiến trúc đã có
├── image_1.png                       # File ảnh tại root
└── emotion.jpg                       # File ảnh tại root
```

## 2. Các lớp trong hệ thống

| Phần | Trách nhiệm | File nên đọc đầu tiên |
| --- | --- | --- |
| Trang prompt | Nhận prompt ban đầu của người dùng | `prompt_box/index.html`, `prompt_box/prompt.js` |
| Widget | Tạo UI chat, lấy bảng từ Excalidraw, gửi câu hỏi | `widget/src/chatbot-widget.js`, `widget/src/ui/chat/messages.js` |
| API | Nhận HTTP request và điều phối xử lý | `backend/app/main.py`, `backend/app/api/routes/chat.py` |
| Services | OCR, gọi AI, xử lý ảnh, quản lý phiên | `backend/app/services/` |
| Reasoning | Phân tích quan hệ phương trình và gợi ý bước giải | `backend/app/reasoning/pipeline.py` |
| Core / schemas / utils | Cấu hình, đường dẫn, trạng thái, schema, tiện ích | `backend/app/core/`, `backend/app/schemas/`, `backend/app/utils/` |
| Dữ liệu | Snapshot bảng, công thức, ảnh, cache và log | `data/`, `backend/data/`, `backend/logs/` |

## 3. Luồng xử lý chính

### Nhập prompt ban đầu

```text
prompt_box/index.html
  → prompt.js nhận submit
  → lưu sessionStorage["initialWhiteboardPrompt"]
```

Hiện `prompt.js` chưa triển khai chuyển hướng sang ứng dụng Excalidraw; phần chuyển hướng mới nằm trong comment. Lưu prompt không tự động gửi câu hỏi đến backend.

### Chat với ngữ cảnh bảng

```text
Người dùng nhập tin nhắn
  → chatbot-widget.js / ui/chat/input.js
  → ui/chat/messages.js
  → window.__excalidrawChatbotBridge lấy PNG và scene
  → POST /api/chat (question, scene_json, ảnh whiteboard nếu có)
  → api/routes/chat.py
  → OCR + ngữ cảnh công thức + xử lý ảnh/đối tượng theo request
  → services/openai_service.py sinh câu trả lời
  → widget hiển thị Markdown qua Marked và DOMPurify
```

Ứng dụng chủ cần cung cấp bridge Excalidraw. Folder này chứa widget và helper tích hợp; không chứa toàn bộ ứng dụng Excalidraw chủ.

### Công thức và gợi ý bước giải

```text
Nét vẽ → API strokes → gom nhóm công thức → OCR
  → data/equations.json
  → API /api/whiteboard/hints
  → reasoning: đồ thị → frontier → parse → bước tiếp theo → hướng dẫn
```

## 4. Chọn nơi sửa code

| Muốn thay đổi | Nơi sửa |
| --- | --- |
| Giao diện trang nhập prompt | `prompt_box/index.html`, `prompt_box/prompt.css` |
| Submit hoặc chuyển trang sau khi nhập prompt | `prompt_box/prompt.js` |
| Khung chat, header, nút mở/đóng | `widget/src/ui/`, `widget/src/styles/` |
| Nội dung gửi backend và cách hiển thị câu trả lời | `widget/src/ui/chat/messages.js` |
| Kết nối với bảng Excalidraw | `widget/src/integrations/excalidraw.js` và bridge của ứng dụng chủ |
| Xử lý request chat | `backend/app/api/routes/chat.py` |
| Cách gọi AI và xây dựng lời nhắc cho AI | `backend/app/services/openai_service.py` và phần dựng ngữ cảnh trong route chat |
| OCR và trích xuất công thức | `backend/app/services/paddle/`, `backend/app/services/equation_ocr.py` |
| Logic gợi ý toán | `backend/app/reasoning/` |
| Cấu hình backend hoặc đường dẫn dữ liệu | `backend/app/core/config.py`, `backend/app/core/paths.py` |

## 5. Ghi chú về cấu trúc hiện tại

- `data/` tại root và `backend/data/` đều đang có file. `backend/app/core/paths.py` quy định đường dẫn ở root; một số phần khác sử dụng đường dẫn tương đối nên nơi lưu thực tế còn phụ thuộc thư mục chạy backend.
- `state_store.py` giữ trạng thái trong RAM; API snapshot bảng có phần lưu trên đĩa. Hai loại trạng thái có vòng đời khác nhau.
- `widget/package.json` chưa có script build thực tế; script test hiện chỉ báo chưa có test. Widget dùng ES modules và dependency npm nên cần cơ chế tích hợp/build từ ứng dụng chủ.
- Bản mô tả dựa trên mã nguồn hiện có, không xác nhận hệ thống đã chạy end-to-end.
