# Phân tích train: raw và clean

Thí nghiệm dùng cùng model `yolo26n.pt`, 20 epoch, batch 16, ảnh 640 px, cùng hai seed (`0`, `1`), cùng tập validation `gold_val` và tập test 100 ảnh. Hai biến thể chỉ khác dữ liệu train. Số liệu tổng hợp lấy từ `comparison.md`; AP50 từng lớp lấy từ bốn file kết quả theo seed.

## 1. Chênh lệch mAP50 và độ nhiễu giữa seed

`mAP50(clean) − mAP50(raw) = 0.7294 − 0.7258 = +0.0036`, hiển thị làm tròn thành `+0.004` trong [comparison.md](comparison.md). Độ lệch chuẩn giữa hai seed là `0.0002` với raw và `0.0024` với clean. Chênh lệch trung bình quan sát được nhỏ, chỉ khoảng 1,5 lần độ lệch chuẩn của clean. Với hai seed và tập test 100 ảnh, chưa đủ bằng chứng để kết luận clean tốt hơn raw một cách ổn định; kết quả hiện tại chỉ cho thấy mAP50 của clean nhỉnh hơn nhẹ trong lần thử này.

Các chỉ số khác cũng không đồng loạt tốt hơn: mAP50-95 là `0.5117` ở raw và `0.4996` ở clean; precision là `0.7635` và `0.7936`; recall là `0.6490` và `0.6193`. Vì vậy không nên chỉ dựa vào mAP50 để kết luận chất lượng tổng thể.

## 2. Số ảnh raw thực sự được dùng để train

Tập raw được dựng ban đầu từ **224 ảnh** và **224 file nhãn**; đây là số đầu vào trước khi Ultralytics kiểm tra dữ liệu. Log train ở Colab liệt kê **11 ảnh/nhãn bị bỏ qua** với thông báo `ignoring corrupt image/label` (cùng 11 trường hợp đó xuất hiện ở cả hai seed). Vì vậy, dựa trên các đường dẫn bị loại cụ thể, còn **213/224 ảnh** được giữ lại để train. Log cũng ghi 19 backgrounds; đây là ảnh không có box nhãn hợp lệ để tính đối tượng, không nên cộng/trừ riêng như một số ảnh bị loại.

Dòng tổng hợp trong log ghi `216 images, 19 backgrounds, 11 corrupt` trên `224/224` ảnh. Các nhóm đếm này không cộng thành 224, nên con số 213 ở trên được tính từ 224 ảnh đầu vào trừ 11 đường dẫn bị Ultralytics báo bỏ qua, chứ không lấy số `216 images` làm tổng mẫu train. File JSON do script sinh vẫn ghi `train_images: 224` vì đó là số file đầu vào trước bước lọc của Ultralytics.

## 3. Rò rỉ ảnh test vào raw

Có bằng chứng **11 ảnh raw** bị phát hiện trùng với ảnh trong kho test/val: các dòng `LEAK_TEST` trong [01_intake.csv](../reports/01_intake.csv) liệt kê 11 stem khác nhau, mỗi dòng chỉ ra ảnh tương ứng trong test. Script train raw đưa toàn bộ `data/raw/images` vào tập train, nên các ảnh đó cũng nằm trong đầu vào của biến thể raw.

Điều này có thể làm điểm raw trên test cao giả tạo vì một số ảnh test đã xuất hiện trong dữ liệu train. Tuy nhiên, thí nghiệm hiện tại không đo riêng mức tăng do rò rỉ; không thể suy ra chính xác raw bị tăng bao nhiêu điểm mAP từ kết quả raw/clean này. Muốn đo cần chạy một đối chứng raw đã loại 11 ảnh rò rỉ, giữ nguyên model, epoch, seed, validation và test, rồi so sánh với raw hiện tại. Vì vậy chênh lệch raw-clean hiện tại bị ảnh hưởng bởi rò rỉ và không phải phép so sánh hoàn toàn sạch.

## 4. AP50 theo lớp

Trung bình AP50 của mỗi lớp được tính từ hai seed trong `raw_seed0.json`, `raw_seed1.json`, `clean_seed0.json` và `clean_seed1.json`.

| Lớp | Raw AP50 trung bình | Clean AP50 trung bình | Chênh clean − raw |
|---|---:|---:|---:|
| car | 0.7375 | 0.7530 | +0.0155 |
| person | 0.8221 | 0.8277 | +0.0057 |
| truck | 0.6485 | 0.6215 | −0.0270 |
| bus | 0.6949 | 0.7153 | **+0.0204** |

`bus` tăng nhiều nhất về AP50 trung bình; `truck` giảm nhiều nhất. Có thể là việc sửa nhãn lỗi trong raw có lợi cho một số lớp, trong khi clean vẫn còn nhãn chưa hoàn hảo. Báo cáo lỗi ban đầu [02_error_list_v1.txt](../reports/02_error_list_v1.txt) có các cảnh báo ngữ nghĩa như `POSSIBLE_WRONG_CLASS`, `POSSIBLE_MISSING`, `POSSIBLE_FALSE_POS` và `POSSIBLE_LOOSE_BOX`, có thể ảnh hưởng đến AP. Tuy nhiên, các số liệu hiện có không chứng minh những lỗi đó tập trung ở lớp bus hay truck; cần kiểm tra nhãn và box theo lớp trước khi khẳng định nguyên nhân. Hai seed cũng khiến chênh lệch theo lớp còn chưa ổn định.

## 5. Lỗi còn lại trong clean và giới hạn của kết quả

Hàng đợi ban đầu có **121 ảnh**, trong khi ngân sách mô phỏng duyệt là **80 ảnh**, nên vượt ngân sách 41 ảnh. Sau mô phỏng, [08_summary.json](../reports/08_summary.json) ghi còn cảnh báo trên `34/193` ảnh (`17.62%`) và quyết định là **Hold**. Danh sách sau duyệt [07_error_list_v3.txt](../reports/07_error_list_v3.txt) vẫn có cảnh báo, gồm `BOX_TINY`, `BOX_HUGE`, `EMPTY_LABEL` và các cảnh báo từ `second_opinion`; không còn lỗi bắt buộc trong lần chạy chính.

Vì vậy `clean` ở thí nghiệm này **không phải nhãn sạch tuyệt đối hay chặn trên oracle**. Đây là output pipeline có 193 ảnh, trong đó một phần ảnh đã được người duyệt mô phỏng thay nhãn, nhưng vẫn còn cảnh báo chưa xử lý và chính pipeline kết luận Hold. Kết quả train cho thấy clean không làm mAP50-95 tăng và recall thấp hơn raw; chưa thể tuyên bố clean tốt hơn. Hướng tiếp theo là xử lý các cảnh báo còn lại, đặc biệt các ảnh ngoài ngân sách duyệt, sau đó chạy lại pipeline và thí nghiệm với cùng thiết lập.
