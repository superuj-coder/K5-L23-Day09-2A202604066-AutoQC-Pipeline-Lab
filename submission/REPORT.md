# Báo cáo Day 09 — Đỗ Tuấn Long, 2A202604066

## 1. Kết luận trước

Pipeline kết luận **Hold**: cửa intake quét 224 ảnh raw, loại 31 ảnh ở bước nhận dữ liệu và đưa 193 ảnh vào QC; dataset xuất có 193 ảnh. Sau khi mô phỏng duyệt 80 ảnh, vẫn còn cảnh báo chưa duyệt trên 34/193 ảnh (17,62%), cao hơn ngưỡng Hold 10%. Không còn lỗi bắt buộc ở kết quả cuối (`n_errors = 0`), nhưng tỷ lệ cảnh báo còn lại khiến pipeline chưa được Release.

## 2. Lỗi và phân việc

Số dưới đây đếm issue trong `02_error_list_v1.csv`; cột “ảnh” là số ảnh khác nhau có mã đó. Một ảnh có thể có nhiều issue. Các lỗi `BAD_CLASS_NAME` cùng nằm trên `data.yaml`, vì vậy 2 issue nhưng chỉ 1 mục dữ liệu.

| Mã lỗi | Số ảnh / issue | Ai xử lý | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2 / 2 | Máy | Ảnh hỏng, không đọc được; bị loại ở intake. |
| `BAD_SIZE` | 3 / 3 | Máy | Cạnh ngắn dưới ngưỡng 250 px; bị loại ở intake. |
| `DUP_IMAGE_NEAR` | 7 / 7 | Máy | Ảnh trùng gần đúng; bị loại ở intake theo ngưỡng pHash đã calibrate. |
| `DUP_IMAGE_EXACT` | 8 / 8 | Máy | Ảnh trùng byte; giữ một bản, loại bản lặp. |
| `LEAK_TEST` | 11 / 11 | Máy | Ảnh trùng ảnh trong kho test/val; bị loại để tránh rò rỉ. |
| `BAD_CLASS_ID` | 6 / 6 | Máy | ID lớp ngoài danh sách hợp lệ; xóa dòng nhãn lỗi. |
| `BAD_CLASS_NAME` | 1 / 2 issue | Máy | Tên lớp sai chữ hoa/thường trong `data.yaml`; ghi lại tên theo cấu hình. |
| `BAD_FORMAT` | 3 / 3 | Máy | Dòng nhãn sai định dạng hoặc có `nan`; xóa dòng không đọc được. |
| `BOX_OUT_OF_IMAGE` | 8 / 8 | Máy | Box vượt biên ảnh; cắt box vào ảnh. |
| `BOX_ZERO` | 4 / 4 | Máy | Box có chiều rộng hoặc chiều cao bằng 0; xóa dòng. |
| `DUP_BOX` | 7 / 7 | Máy | Box cùng lớp bị lặp; xóa dòng lặp. |
| `MISSING_LABEL_FILE` | 6 / 6 | Người | Máy không thể tự đoán nhãn còn thiếu; đưa ảnh vào hàng đợi gán nhãn. |
| `EMPTY_LABEL` | 11 / 11 | Người | Cần xem ảnh để phân biệt ảnh nền thật với trường hợp thiếu box. |
| `POSSIBLE_MISSING` | 52 ảnh / 53 issue | Người | Model gợi ý có vật thể chưa được gán nhãn; đây chỉ là cảnh báo. |
| `POSSIBLE_LOOSE_BOX` | 23 ảnh / 27 issue | Người | Box có thể lỏng hoặc lệch so với vật thể. |
| `POSSIBLE_WRONG_CLASS` | 17 / 17 | Người | Model nghi ngờ nhãn gán nhầm lớp. |
| `POSSIBLE_FALSE_POS` | 26 ảnh / 28 issue | Người | Box nhãn không khớp dự đoán model; cần người xác nhận. |
| `BOX_TINY` | 4 ảnh / 6 issue | Người | Box nhỏ hơn ngưỡng; cần xem ngữ cảnh ảnh. |
| `BOX_HUGE` | 3 / 3 | Người | Box chiếm diện tích lớn; cần xác nhận có bao trọn vật thể hay không. |
| `CLASS_RARE` | 1 ảnh / 4 issue | Người | Cảnh báo thống kê lớp hiếm; cần kiểm tra phân bố dữ liệu. |

Hàng đợi xếp theo điểm ưu tiên giảm dần. Điểm cộng trọng số của các cảnh báo và các sửa tự động cần người kiểm; `NEEDS_LABEL` có trọng số cao, nên ảnh chưa có file nhãn được đẩy lên đầu. Nếu bằng điểm, tên ảnh dùng để sắp thứ tự. Hàng đợi có 121 ảnh, nhưng ngân sách chỉ duyệt 80 ảnh. Trong 80 ảnh đầu, các mã ngữ nghĩa xuất hiện trên số ảnh như sau: `POSSIBLE_MISSING` 51, `POSSIBLE_WRONG_CLASS` 17, `POSSIBLE_LOOSE_BOX` 8, `POSSIBLE_FALSE_POS` 12. Một ảnh có thể có nhiều mã, nên các số này không cộng thành số ảnh duyệt.

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | 16 | `DUP_IMAGE_NEAR`: 1,00 / 0,50 → 1,00 / 0,83; `DUP_IMAGE_EXACT` giữ 1,00 / 1,00 | Mức 16 bắt được nhiều ảnh trùng gần đúng hơn mà precision trên calib vẫn 1,00. Mức 20 làm recall giảm và có thể loại nhầm ảnh tốt. |
| `second_opinion.conf` | 0,25 | 0,6 | `WRONG_CLASS`: 0,56 / 0,83 → 0,62 / 0,83; `MISSING`: 0,50 / 1,00 → 0,57 / 1,00; `LOOSE_BOX`: 0,29 / 0,40 → 0,20 / 0,20; `FALSE_POS`: 0,31 / 1,00 → 0,31 / 1,00 | 0,6 cải thiện precision của cảnh báo nhầm lớp và bỏ sót vật thể mà vẫn giữ recall của hai loại này. Với box lỏng, precision/recall giảm. |


## 4. Cửa chặn và điều pipeline không bắt được

Kết quả chạy chính chứng minh cửa chặn đã giữ lô: [submission/reports/08_summary.json](reports/08_summary.json) ghi `Hold`, 34/193 ảnh còn cảnh báo chưa duyệt, tỷ lệ 17,62% so với ngưỡng 10%. Kết quả cuối có 0 lỗi bắt buộc. Đã chạy lệnh `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`: pipeline còn 6 lỗi bắt buộc sau sửa tự động nên kết luận `Rework`.

Các ảnh đã kiểm tra cho thấy cảnh báo của model hữu ích nhưng cần người xác nhận:

- `img_0030`: một số người chưa có bounding box; một số box khác bắt được người nhưng ước lượng chưa đúng vì người chỉ lộ phần chân. Pipeline có cảnh báo `POSSIBLE_FALSE_POS` tại `img_0030.txt:9` trong [submission/reports/02_error_list_v1.txt](reports/02_error_list_v1.txt). Kết luận cảnh báo có thể dựa dẫm
- `img_0018`: cảnh báo `POSSIBLE_LOOSE_BOX` đúng; ảnh có một cậu bé đắp chăn, chỉ lộ nửa thân trên. Box cần ôm sát phần thân nhìn thấy thay vì bao vùng chăn/nền rộng hơn. Đây là ví dụ lỗi box mà checker phát hiện được và người cần đánh giá mức box phù hợp với vật thể nhìn thấy.
- `img_0057`: cảnh báo `POSSIBLE_MISSING` đúng; ảnh không có bounding box dù có một người nằm dưới ô. Đây là vật thể bị bỏ sót trong nhãn; cần người thêm box sau khi kiểm tra ảnh.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Đã train `yolo26n.pt` trong 20 epoch với batch 16, ảnh 640 px và hai seed (0, 1). Raw có 224 ảnh đầu vào; log Ultralytics báo bỏ qua 11 ảnh/nhãn lỗi, còn 213 ảnh theo các đường dẫn bị loại cụ thể. mAP50 trung bình là 0,7258 (raw) và 0,7294 (clean), chênh +0,0036; với hai seed và test 100 ảnh, chưa đủ bằng chứng kết luận clean tốt hơn ổn định. `bus` tăng AP50 nhiều nhất (+0,0204), còn `truck` giảm nhiều nhất (−0,0270). Raw có 11 ảnh bị phát hiện trùng với test/val nên kết quả raw có nguy cơ bị thổi phồng; thí nghiệm này chưa đo riêng mức ảnh hưởng. Phân tích đủ năm câu hỏi và các giới hạn được ghi tại [submission/results/ANALYSIS.md](results/ANALYSIS.md).

## 6. Quyết định và ghi chú AI

Quyết định hiện tại là **Hold**. Để lô có thể được xem xét Release, cần người xử lý các cảnh báo còn lại; đặc biệt hàng đợi có 121 ảnh nhưng mô phỏng chỉ duyệt 80 ảnh, và gate giữ lô khi ít nhất 10% ảnh còn cảnh báo chưa duyệt.

**Ghi chú AI:** Sử dụng AI để hướng dẫn làm vì các file trong repo quá rời rạc. Có sử dụng AI để viết code, nhưng đã tự review và tối ưu.
