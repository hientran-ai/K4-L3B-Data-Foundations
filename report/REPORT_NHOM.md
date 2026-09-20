# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** G

**Thành viên:** Bùi Phương Duy; Nguyễn Hải Nam; Trần Thị Thu Hiền (2A202602737); Nguyễn Trần Bảo Tâm

**Ngày:** 20/09/2026

> **Nộp 1 bản / nhóm.** Phần cá nhân của từng thành viên nằm trong `REPORT_CANHAN.md`. Bảng so sánh chính thức dùng cùng corpus, benchmark và embedding backend cho cả bốn chiến lược.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề và lý do chọn

**Chủ đề:** Chính sách trả hàng, hoàn tiền, bảo hành và quy định người bán trên Shopee Việt Nam.

Nhóm chọn chủ đề này vì các chính sách có cấu trúc điều khoản rõ ràng, chứa nhiều mốc thời gian và điều kiện có thể kiểm chứng. Corpus đồng thời có tài liệu dành riêng cho người mua và người bán, phù hợp để đánh giá tác động của metadata filter đối với retrieval.

### Danh sách tài liệu

| # | Tên tài liệu | Nguồn | Ngày lấy / Phiên bản | Số ký tự | Metadata chính |
|---|--------------|-------|----------------------|----------:|----------------|
| 1 | Chính sách bảo hành sản phẩm | [Shopee Help](https://help.shopee.vn/portal/4/article/79046) | 20/09/2026 / not-stated | 3.599 | buyer, warranty-policy, vi |
| 2 | Chính sách chống gian lận người bán | [Shopee Help](https://help.shopee.vn/portal/4/article/140097) | 20/09/2026 / hiệu lực 28/12/2023 | 6.800 | seller, seller-regulations, vi |
| 3 | Trả hàng/hoàn tiền — Người Bán | [Shopee Help](https://help.shopee.vn/portal/4/article/77251) | 20/09/2026 / hiệu lực 11/03/2026 | 8.127 | seller, returns-policy, vi |
| 4 | Trả hàng/hoàn tiền — Người Mua | [Shopee Help](https://help.shopee.vn/portal/4/article/77251) | 20/09/2026 / hiệu lực 11/03/2026 | 15.923 | buyer, returns-policy, vi |
| 5 | Điều khoản dịch vụ Shopee Mall | [Shopee Help](https://help.shopee.vn/portal/4/article/77262) | 20/09/2026 / hiệu lực 08/05/2026 | 25.950 | seller, seller-regulations, vi |
| 6 | Phương thức và phí gửi hàng hoàn trả | [Shopee Help](https://help.shopee.vn/portal/4/article/189477) | 20/09/2026 / not-stated | 6.105 | buyer, returns-policy, vi |
| 7 | Quy chế hoạt động sàn Shopee | [Shopee Help](https://help.shopee.vn/portal/4/article/77245) | 20/09/2026 / hiệu lực 10/01/2025 | 10.002 | both, platform-terms, vi |
| 8 | Quy định chung trả hàng/hoàn tiền | [Shopee Help](https://help.shopee.vn/portal/4/article/188931) | 20/09/2026 / not-stated | 6.505 | buyer, returns-policy, vi |
| 9 | Quy định đăng bán sản phẩm | [Shopee Help](https://help.shopee.vn/portal/4/article/77246) | 20/09/2026 / hiệu lực 21/08/2024 | 21.695 | seller, seller-regulations, vi |

Corpus nằm trong `data/chinh-sach-shopee/`; file `sources.csv` có đúng 9 dòng tương ứng 9 tài liệu.

**Danh sách kiểm tra quản trị dữ liệu:**

- [x] Chỉ dùng nguồn công khai, không chứa thông tin đăng nhập hoặc dữ liệu cá nhân.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version`.
- [x] Mỗi tài liệu có `doc_id`, `title`, `audience`, `category`, `language`.
- [x] Corpus có 4 tài liệu buyer, 4 tài liệu seller và 1 tài liệu both.
- [x] Chính sách chung trả hàng được tách thành bản buyer và seller để filter có ý nghĩa.
- [x] `sources.csv` khớp một-một với các file Markdown.

### Cấu trúc Metadata

| Trường metadata | Kiểu | Ví dụ | Tại sao hữu ích? |
|----------------|------|-------|------------------|
| `doc_id` | string | `shopee-chinh-sach-tra-hang-hoan-tien-nguoi-mua` | Truy vết và xóa mọi chunk của tài liệu gốc |
| `title` | string | Chính sách Trả hàng và Hoàn tiền | Hiển thị nguồn dễ đọc |
| `source_url` | URL | `https://help.shopee.vn/...` | Kiểm chứng thông tin với nguồn gốc |
| `retrieved_at` | date | `2026-09-20` | Theo dõi độ mới của dữ liệu |
| `document_version` | string | `hieu-luc-2026-03-11` | Nhận biết phiên bản/ngày hiệu lực |
| `audience` | enum | buyer / seller / both | Ngăn lấy nhầm chính sách của đối tượng khác |
| `category` | string | returns-policy | Thu hẹp theo loại chính sách |
| `language` | string | vi | Chọn mô hình/ngôn ngữ phù hợp |
| `section_path` | string | Chính sách > Điều kiện > 3.1 | Truy vết section của từng chunk |
| `chunk_index` | integer | 4 | Phân biệt các chunk cùng tài liệu |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

### Phân tích đường cơ sở

Chạy `ChunkingStrategyComparator().compare()` với `chunk_size=400` sau khi bỏ YAML frontmatter:

| Tài liệu | Chiến lược | Số chunk | Độ dài trung bình | Nhận xét |
|----------|------------|----------:|------------------:|----------|
| Trả hàng/hoàn tiền — Người Mua | FixedSize | 45 | 394,4 | Kích thước đều nhưng có thể cắt giữa điều khoản |
| Trả hàng/hoàn tiền — Người Mua | Sentence | 40 | 386,7 | Giữ câu, tạo nhiều chunk ngắn hơn |
| Trả hàng/hoàn tiền — Người Mua | Recursive | 52 | 296,5 | Giữ đoạn/câu tốt hơn fixed-size |
| Chính sách bảo hành | FixedSize | 10 | 365,1 | Có overlap nhưng có thể cắt ngang điều kiện |
| Chính sách bảo hành | Sentence | 5 | 637,6 | Giữ nguyên ranh giới câu |
| Chính sách bảo hành | Recursive | 10 | 313,8 | Ưu tiên ranh giới tự nhiên |
| Quy định đăng bán sản phẩm | FixedSize | 61 | 398,6 | Kích thước đều, phù hợp baseline |
| Quy định đăng bán sản phẩm | Sentence | 78 | 270,5 | Có thể tách rời heading và nội dung |
| Quy định đăng bán sản phẩm | Recursive | 66 | 318,2 | Cân bằng kích thước và ranh giới văn bản |

### Chiến lược của từng thành viên

**Bùi Phương Duy — FixedSizeChunker**

- **Tham số:** `chunk_size=500`, `overlap=50`.
- **Lý do chọn:** Đây là baseline đơn giản, không phụ thuộc cấu trúc văn bản. Overlap giảm rủi ro một câu hoặc điều khoản bị cắt đúng ranh giới chunk.

**Nguyễn Trần Bảo Tâm — RecursiveChunker**

- **Tham số:** `chunk_size=400`.
- **Lý do chọn:** Ưu tiên ranh giới tự nhiên như đoạn, dòng và câu trước khi cắt nhỏ hơn, nhờ đó ít làm vỡ câu hơn fixed-size.

**Trần Thị Thu Hiền — HeadingChunker**

- **Tham số chính thức:** `chunk_size=800`.
- **Mô tả:** Nhận diện Markdown heading và các đề mục đánh số ngắn. Heading cha được gắn lại vào từng chunk để giữ đường dẫn section; section dài được chuyển xuống RecursiveChunker.
- **Lý do chọn:** Với tài liệu chính sách, một section thường là một đơn vị ngữ nghĩa tương đối hoàn chỉnh, phù hợp cho câu hỏi cần nhiều điều kiện hoặc nhiều mốc thời gian.

**Nguyễn Hải Nam — ClauseChunker**

- **Tham số:** `max_chars=400`.
- **Mô tả:** Tách theo điều/khoản/điểm như `1.`, `1.1.`, `a.`, `ii.`. Chunk nhỏ hơn giúp tăng mật độ đáp án cho câu hỏi tra một con số hoặc một quy định cụ thể.
- **Code:** `src/clause_chunker.py`.

### So sánh giữa các thành viên

Phép chạy đối chứng chung dùng `text-embedding-3-small`, cùng corpus 9 tài liệu, cùng năm benchmark query và cùng `top_k=3`. Cột **Nội dung** chỉ tính đúng khi chunk chứa bằng chứng của gold answer; cột **Doc-id** chỉ kiểm tra đúng tài liệu.

| Thành viên | Chiến lược | Số chunk | Độ dài TB | Doc-id (/10) | Nội dung (/10) | Điểm mạnh | Điểm yếu |
|-----------|------------|----------:|-----------:|-------------:|---------------:|-----------|----------|
| Bùi Phương Duy | FixedSizeChunker (500, overlap 50) | 229 | 489,2 | 8 | **5** | Kích thước đều; overlap giữ thông tin qua ranh giới | Có thể cắt ngang điều khoản và trộn nhiều ý |
| Nguyễn Trần Bảo Tâm | RecursiveChunker (400) | 325 | 307,2 | 9 | **7** | Tôn trọng ranh giới tự nhiên, ít vỡ câu | Không hiểu cấu trúc điều/khoản |
| Trần Thị Thu Hiền | HeadingChunker (800) | 167 | 642,4 | 8 | **9** | Section là đơn vị ngữ nghĩa trọn vẹn, giữ đủ ngữ cảnh | Các section cùng chủ đề có thể cạnh tranh điểm gần nhau |
| Nguyễn Hải Nam | ClauseChunker (400) | 491 | 250,6 | 9 | **7** | Mật độ đáp án cao, tốt cho câu hỏi tra một số liệu | Có thể tách danh sách đáp án thành nhiều chunk; phụ thuộc regex |

**Chiến lược nào tốt nhất cho chủ đề này?**

HeadingChunker đạt cao nhất với **9/10**. Kết quả này cho thấy chunk càng nhỏ chưa chắc càng tốt: ClauseChunker tạo 491 chunk, gần gấp ba HeadingChunker, nhưng chỉ đạt 7/10. Điểm `doc_id` của bốn chiến lược gần nhau, nên khác biệt chính nằm ở việc chunk top-3 có chứa đầy đủ bằng chứng hay không. Với văn bản có cấu trúc mục rõ ràng, đơn vị chunk nên khớp với đơn vị trả lời thay vì chỉ tối thiểu hóa kích thước.

Kết quả cũng cho thấy embedding backend phải được thống nhất. Cùng một ClauseChunker và corpus, MockEmbedder có thể cho kết quả rất thấp trong khi embedding ngữ nghĩa đạt 7/10; nếu dùng backend khác nhau, bảng sẽ đo chất lượng embedding thay vì chiến lược chunking.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá và Gold Answer

| # | Câu hỏi | Gold Answer | Chunk chứa thông tin |
|---|---------|-------------|-----------------------|
| 1 | Bảo hành sản phẩm thông qua Shopee mất bao lâu? | Dự kiến từ 20 đến 45 ngày làm việc tính từ lúc Shopee nhận được sản phẩm | Bảo hành > 4.b. Bảo hành thông qua Shopee |
| 2 | Sản phẩm cần thỏa những điều kiện gì để được bảo hành miễn phí? | Lỗi kỹ thuật do nhà sản xuất; còn hạn; có hóa đơn điện tử hoặc mã đơn hàng; phiếu/tem bảo hành còn nguyên vẹn với đồ điện gia dụng | Bảo hành > 1. Điều kiện bảo hành |
| 3 | Thời hạn gửi yêu cầu Trả hàng/Hoàn tiền với từng loại đơn hàng là bao lâu? | Đơn thường: 15 ngày; thực phẩm tươi sống/đông lạnh: 24 giờ; chưa bấm “Đã nhận được hàng”: 20 ngày từ lúc lấy hàng thành công | Quy định chung > 1.2. Thời gian tối đa |
| 4 | Người bán được đăng bán hàng hóa còn bao nhiêu hạn sử dụng? | Ít nhất 30% thời hạn sử dụng và ít nhất 30 ngày đến ngày hết hạn | Đăng bán > Quy định hạn sử dụng |
| 5 | Bên liên quan có bao nhiêu ngày để xử lý yêu cầu trả hàng/hoàn tiền? | `buyer`: gửi yêu cầu trong 15 ngày; `seller`: phản hồi trong 02 ngày lịch | Chính sách Người Mua > 3.2; Chính sách Người Bán > 3 |

### Tổng hợp chất lượng truy xuất của nhóm

| # | Câu hỏi | Chiến lược tốt nhất | Kết quả | Nhận xét |
|---|---------|---------------------|---------|----------|
| 1 | Bảo hành thông qua Shopee mất bao lâu? | HeadingChunker | Heading đạt 2/2 | Các chiến lược khác lấy đúng tài liệu nhưng chunk chứa mốc 20–45 ngày không đứng top-1 |
| 2 | Điều kiện bảo hành miễn phí là gì? | ClauseChunker | Clause đạt 2/2 | Clause đưa đúng khoản điều kiện lên top-1; các chiến lược khác có thể lấy chunk cùng chủ đề nhưng thiếu một phần gold |
| 3 | Thời hạn theo từng loại đơn hàng? | RecursiveChunker và HeadingChunker | Có đủ nội dung | Chunk quá nhỏ dễ tách 15 ngày, 24 giờ và 20 ngày thành nhiều mảnh |
| 4 | Hạn sử dụng tối thiểu? | Cả bốn chiến lược | Đều có chunk liên quan | Hai con số nằm gọn trong một đoạn nên ít phụ thuộc chiến lược |
| 5 | Thời hạn xử lý theo buyer/seller? | Cả bốn khi dùng filter | Đúng theo từng audience | Đây là câu bắt buộc kiểm tra metadata filter |

**Kết quả chính thức theo nội dung:** FixedSize 5/10; Recursive 7/10; Heading 9/10; Clause 7/10. Kết quả cục bộ bằng lexical hash trong `ket_qua_benchmark.txt` chỉ là phép chạy chẩn đoán không cần API; bảng chính thức dùng chung `text-embedding-3-small` để so sánh công bằng.

### Tác động của metadata filter

Câu 5 được chạy không filter, với `audience=buyer` và với `audience=seller`. Không filter, top-3 có thể trộn hai đối tượng; filter ép retrieval về đúng phía và lần lượt tìm mốc 15 ngày hoặc 02 ngày lịch. Trong lần chạy đối chứng, cả bốn chiến lược đều thay đổi top-k khi áp dụng filter. `KnowledgeBaseAgent.answer()` cũng nhận `metadata_filter` và gọi `search_with_filter()` để bảo đảm câu trả lời cuối không bỏ qua kết quả đã lọc.

### Phân tích lỗi

Chấm theo `doc_id` có thể thổi phồng kết quả vì lấy đúng tài liệu chưa chắc chunk top-3 chứa đủ đáp án. Chunk theo điều/khoản tốt cho câu hỏi tra một số liệu, nhưng có thể làm hỏng câu hỏi cần liệt kê nhiều mốc. Ngược lại, chunk lớn giữ ngữ cảnh nhưng dễ trộn nhiều sự thật. Vì vậy nhóm chấm riêng doc-level và content-level, đồng thời dùng cùng embedding backend cho mọi chiến lược.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những insight dự kiến trình bày:**

- Việc tách chính sách chung thành buyer/seller giúp metadata filter tạo khác biệt có thể quan sát.
- HeadingChunker đạt 9/10 vì đơn vị section phù hợp với đơn vị trả lời của văn bản chính sách.
- Đúng `doc_id` chưa đủ: phải kiểm tra chunk có chứa số liệu/gold answer hay không.
- Agent phải truyền metadata filter xuống vector store; nếu chỉ gọi `search()`, câu trả lời vẫn có thể sai đối tượng.

**Bài học rút ra khi so sánh trong nhóm:**

Cùng một corpus nhưng chiến lược chunking làm thay đổi mạnh số lượng chunk và độ mạch lạc của ngữ cảnh. Chunk nhỏ theo điều/khoản tốt cho câu hỏi tra một số liệu, nhưng dễ làm hỏng câu hỏi cần liệt kê nhiều mốc; chunk theo heading giữ ngữ cảnh tốt hơn nhưng có thể khiến các section cùng chủ đề cạnh tranh điểm gần nhau. Kết luận quan trọng là chunk nên khớp với đơn vị trả lời, không phải càng nhỏ càng tốt.

**Nếu làm lại, nhóm sẽ thay đổi gì?**

Nhóm sẽ chuẩn hóa metadata `audience` sớm, tách riêng tài liệu có nhiều đối tượng, thêm bộ kiểm thử riêng cho filter và ghi rõ chuỗi đáp án kỳ vọng cho từng query. Nhóm cũng sẽ lưu cả điểm doc-level, content-level và answer-level thay vì chỉ nhìn cosine score.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu | 10 / 10 |
| Thiết kế chiến lược | 14 / 15 |
| Chất lượng truy xuất | 9 / 10 |
| Thuyết trình | 4 / 5 |
| **Tổng phần nhóm** | **37 / 40** |
