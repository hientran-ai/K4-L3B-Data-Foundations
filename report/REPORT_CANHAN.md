# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Trần Thị Thu Hiền

**Mã sinh viên:** 2A202602737

**Nhóm:** [Bổ sung tên nhóm]

**Ngày:** 20/09/2026

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**

Độ tương tự cosine cao nghĩa là hai vector embedding có hướng gần giống nhau. Trong xử lý văn bản, điều này thường cho thấy hai câu hoặc hai đoạn đang biểu đạt nội dung, chủ đề hoặc ý nghĩa tương tự, dù có thể dùng từ ngữ khác nhau.

**Ví dụ có độ tương tự CAO:**

- Câu A: Người mua muốn yêu cầu hoàn tiền.
- Câu B: Khách hàng cần biết quy trình nhận lại tiền.
- Tại sao tương đồng: Hai câu đều nói về nhu cầu hoàn tiền của người mua, chỉ khác cách diễn đạt.

**Ví dụ có độ tương tự THẤP:**

- Câu A: Sản phẩm phải còn nguyên tem để được đổi trả.
- Câu B: Hôm nay thời tiết tại Hà Nội có mưa.
- Tại sao khác: Một câu nói về điều kiện đổi trả hàng hóa, câu còn lại nói về thời tiết nên hầu như không có chung ý nghĩa.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**

Cosine similarity tập trung vào góc, hay hướng, giữa hai vector thay vì độ lớn tuyệt đối. Vì ý nghĩa của text embedding thường được thể hiện chủ yếu qua hướng vector, cosine ít bị ảnh hưởng bởi độ dài vector và phù hợp hơn để so sánh mức độ tương đồng ngữ nghĩa.

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**

Áp dụng công thức:

```text
ceil((document_length - overlap) / (chunk_size - overlap))
= ceil((10,000 - 50) / (500 - 50))
= ceil(9,950 / 450)
= ceil(22.111...)
= 23 chunks
```

**Đáp án:** 23 chunks.

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**

```text
ceil((10,000 - 100) / (500 - 100))
= ceil(9,900 / 400)
= ceil(24.75)
= 25 chunks
```

Số chunk tăng từ 23 lên 25. Overlap lớn hơn giúp giữ lại ngữ cảnh tại ranh giới giữa hai chunk và giảm nguy cơ một ý quan trọng bị cắt đôi, nhưng đồng thời làm tăng dữ liệu trùng lặp, dung lượng lưu trữ và chi phí embedding.

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk` — hướng tiếp cận:**

Tôi dùng biểu thức chính quy `(?<=[.!?])(?:[ \t]+|\r?\n+)` để tách tại khoảng trắng hoặc xuống dòng nằm sau dấu kết thúc câu, nhờ đó dấu câu vẫn được giữ lại. Các câu sau khi làm sạch được gom theo `max_sentences_per_chunk`; văn bản rỗng trả về danh sách rỗng. Cách tách đơn giản này có thể nhận diện chưa chính xác chữ viết tắt như `TS.` hoặc một số trường hợp số thập phân.

**`RecursiveChunker.chunk` / `_split` — hướng tiếp cận:**

Thuật toán thử các separator theo thứ tự ưu tiên `\n\n`, `\n`, `. `, khoảng trắng và cuối cùng là cắt cứng. Đoạn vượt quá `chunk_size` tiếp tục được chia đệ quy bằng separator nhỏ hơn; các mảnh nhỏ liền kề được gom lại đến gần giới hạn để tránh sinh chunk vụn. Các base case gồm văn bản rỗng, văn bản đã đủ ngắn, hết separator và separator rỗng.

### Lớp EmbeddingStore

**`add_documents` + `search` — hướng tiếp cận:**

Mỗi `Document` được chuẩn hóa thành một record trong bộ nhớ gồm ID, nội dung, bản sao metadata và embedding. Metadata luôn có `doc_id` để truy vết tài liệu gốc. Khi search, truy vấn được embed, sau đó tính dot product với các embedding đã lưu, sắp xếp score giảm dần và trả tối đa `top_k` kết quả mà không đưa vector embedding dài vào output.

**`search_with_filter` + `delete_document` — hướng tiếp cận:**

`search_with_filter` lọc các record khớp toàn bộ cặp khóa–giá trị metadata trước khi tính similarity, tránh để tài liệu sai chiếm các vị trí top-k. `delete_document` loại bỏ tất cả record có `metadata["doc_id"]` bằng ID cần xóa và trả về `True` khi có ít nhất một record bị xóa.

### Tác tử KnowledgeBaseAgent

**`answer` — hướng tiếp cận:**

Agent truy xuất top-k chunk rồi tạo context được đánh số `[1]`, `[2]`, `[3]`, kèm nguồn lấy từ `source_url`, `source` hoặc `doc_id`. Prompt yêu cầu mô hình chỉ trả lời dựa trên context, dẫn nguồn theo số chunk và nói rõ khi không đủ thông tin. Nếu store không trả kết quả, agent trả thông báo trực tiếp và không gọi LLM vô ích.

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

Đã hoàn thiện các TODO bắt buộc trong `src/chunking.py`, `src/store.py` và `src/agent.py`.

### Kết Quả Kiểm Thử (Test Results)

Lệnh kiểm thử:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Kết quả thực tế ngày 20/09/2026:

```text
..........................................                               [100%]
42 passed in 0.04s
```

Demo thủ công cũng chạy thành công bằng chế độ UTF-8:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py "Vector store dùng để làm gì?"
```

**Số lượng bài test vượt qua (pass): 42 / 42**

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

Tôi dự đoán dựa trên ý nghĩa câu trước khi chạy. Điểm thực tế bên dưới được tính bằng `MockEmbedder` mặc định và hàm `compute_similarity`; do MockEmbedder sinh vector từ hash MD5 nên các điểm này dùng để kiểm tra luồng tính toán, không đại diện cho chất lượng embedding ngữ nghĩa.

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-------|-------|---------|--------------:|-------|
| 1 | Người mua muốn yêu cầu hoàn tiền. | Khách hàng cần biết quy trình nhận lại tiền. | Cao | -0.067840 | Không |
| 2 | Sản phẩm được bảo hành trong mười hai tháng. | Thời hạn bảo hành của sản phẩm là một năm. | Cao | -0.194768 | Không |
| 3 | Người bán phải phản hồi yêu cầu bảo hành đúng hạn. | Nhà bán hàng cần xử lý đề nghị bảo hành trong thời gian quy định. | Cao | 0.014023 | Không |
| 4 | Sản phẩm phải còn nguyên tem để được đổi trả. | Hôm nay thời tiết tại Hà Nội có mưa. | Thấp | -0.189028 | Có |
| 5 | Người mua gửi yêu cầu đổi trả. | Cơ sở dữ liệu vector lưu trữ embeddings. | Thấp | -0.081503 | Có |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**

Ba cặp đầu có ý nghĩa gần nhau nhưng đều nhận điểm gần 0 hoặc âm, trong đó cặp “mười hai tháng” và “một năm” bất ngờ nhất vì hai câu gần như tương đương. Nguyên nhân là MockEmbedder không học ý nghĩa mà tạo vector giả ngẫu nhiên từ hash của chuỗi. Thí nghiệm cho thấy việc chuẩn hóa vector và tính cosine đúng chưa đủ; chất lượng retrieval còn phụ thuộc quyết định vào mô hình embedding.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Phần này sử dụng đúng bộ 5 câu hỏi và gold answer của `REPORT_NHOM.md`, được khai báo lại trong `bench.py`. Corpus gồm 9 tài liệu công khai từ Trung tâm trợ giúp Shopee trong `data/chinh-sach-shopee/`, kèm `sources.csv`; metadata gồm 4 tài liệu `buyer`, 4 tài liệu `seller` và 1 tài liệu `both`. Chính sách trả hàng/hoàn tiền gốc đã được tách thành bản dành cho người mua và người bán để metadata filter có ý nghĩa thực tế.

Chiến lược cá nhân đã triển khai là **HeadingChunker**. Phép chạy chẩn đoán cục bộ dùng `chunk_size=700` và lexical hash, tạo 260 chunks mà không cần API key. Phép chạy đối chứng chính thức của nhóm dùng `chunk_size=800` và chung `text-embedding-3-small` cho cả bốn chiến lược, tạo 167 chunks cho HeadingChunker. Chunker nhận diện Markdown heading và các đề mục đánh số như `3.`, `3.1.`; section quá dài được chia tiếp bằng RecursiveChunker và toàn bộ đường dẫn heading được gắn lại vào mỗi chunk con.

### Phép chạy chẩn đoán cục bộ

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-----------------|--------------------------------------|------------|--------------------------------|---------------------------------|
| 1 | Bảo hành sản phẩm thông qua Shopee mất bao lâu? | Bảo hành qua Shopee: dự kiến 20–45 ngày làm việc từ lúc nhận sản phẩm | 0.348958 | Có — top-1, đủ gold | Trả lời đúng mốc 20–45 ngày làm việc và dẫn đúng nguồn |
| 2 | Sản phẩm cần thỏa những điều kiện gì để được bảo hành miễn phí? | Top-1 là phần loại trừ; top-2 chứa lỗi kỹ thuật, thời hạn, mã đơn và tem bảo hành | 0.406362 | Chunk chứa gold ở top-2; top-3 đủ các ý | Câu trích xuất tự động chưa tổng hợp đủ bốn điều kiện dù context đã đủ |
| 3 | Thời hạn gửi yêu cầu Trả hàng/Hoàn tiền với từng loại đơn hàng là bao lâu? | Quy định chung: 15 ngày cho đơn thường | 0.496258 | Có — top-1, nhưng top-3 thiếu mốc 24 giờ và 20 ngày | Trả lời được mốc 15 ngày nhưng chưa tổng hợp đủ ba trường hợp |
| 4 | Người bán được đăng bán hàng hóa còn bao nhiêu hạn sử dụng? | Quy định hạn sử dụng: ít nhất 30% và ít nhất 30 ngày | 0.433070 | Có — top-1, đủ gold | Trả lời đúng cả 30% và 30 ngày |
| 5 | Thời hạn xử lý yêu cầu trả hàng/hoàn tiền là bao lâu? | Buyer top-1 cùng chủ đề; seller top-1 đúng tài liệu nhưng đoạn thời hạn nằm ở chunk kế tiếp | 0.509172 / 0.534812 | Không — cả hai nhánh đều thiếu mốc gold trong top-3 | Chưa lấy được `15 ngày` cho buyer và `02 ngày lịch` cho seller |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 4 / 5. Câu 1 và 4 đứng top-1 đồng thời đủ mọi ý của gold answer nên mỗi câu đạt 2 điểm. Câu 2 có chunk đúng ở top-2; câu 3 đứng top-1 nhưng context top-3 chưa đủ ba mốc nên mỗi câu đạt 1 điểm. Câu 5 chỉ được tính đúng khi cả nhánh `buyer` và `seller` đều có mốc gold trong top-3, nhưng cả hai nhánh đều chưa đạt. **Tổng: 6 / 10.**

### Phép chạy đối chứng chính thức của nhóm

Để so sánh công bằng, Nam chạy lại bốn chiến lược trên cùng corpus, cùng năm câu hỏi, `top_k=3` và cùng embedding `text-embedding-3-small`. HeadingChunker `size=800` đạt **8/10 theo doc-id và 9/10 theo nội dung**, cao nhất trong bốn chiến lược; FixedSize đạt 5/10, Recursive đạt 7/10 và Clause đạt 7/10 theo nội dung. Kết quả này được dùng làm điểm competition chính thức của tôi; kết quả lexical 6/10 phía trên được giữ lại như failure analysis để minh họa ảnh hưởng của embedding backend.

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**

Từ phép chạy đối chứng của Nam, tôi học được rằng chunk nhỏ hơn không mặc nhiên tốt hơn: ClauseChunker tạo gần gấp ba số chunk của HeadingChunker nhưng mất ngữ cảnh ở câu hỏi cần liệt kê nhiều mốc. Kết quả của các thành viên cũng cho thấy phải dùng cùng embedding backend trước khi so sánh chunking; nếu không, chênh lệch điểm có thể đến từ mô hình embedding thay vì chiến lược dữ liệu.

### Phân tích lỗi

Ở câu 2, chunk top-1 là phần loại trừ vì lặp nhiều từ “điều kiện bảo hành”; chunk tích cực chứa đủ bốn điều kiện đứng top-2. Ở câu 3, top-1 đúng section nhưng việc chia section dài khiến ba mốc 15 ngày, 24 giờ và 20 ngày không cùng xuất hiện trong top-3. Câu 5 là failure case rõ nhất: lexical embedding xếp các chunk cùng chủ đề “xử lý yêu cầu trả hàng/hoàn tiền” lên cao, còn câu chứa con số cụ thể nằm ngoài top-3. Có thể cải thiện bằng embedding tiếng Việt có ngữ nghĩa, overlap giữa các chunk con hoặc reranking theo tín hiệu thời gian.

Với câu 5, khi bỏ metadata filter, top-3 trộn cả tài liệu `seller` và `buyer`. Khi chạy riêng `metadata_filter={"audience": "buyer"}` và `metadata_filter={"audience": "seller"}`, hệ thống không còn lẫn đối tượng, nhưng filter không tự giải quyết được việc chunk chứa mốc thời gian xếp thấp. Điều này cho thấy metadata filter tăng precision theo đối tượng, còn chất lượng xếp hạng vẫn phụ thuộc chunking và embedding.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 9 / 10 |
| **Tổng phần cá nhân tạm thời** | **59 / 60** |

> Điểm retrieval chính thức dựa trên phép chạy đối chứng chung bằng `text-embedding-3-small` ghi trong `REPORT_NHOM.md`; `ket_qua_benchmark.txt` là phép chạy cục bộ bằng lexical hash dùng cho phân tích lỗi.
