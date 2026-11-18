"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    rules = cfg["second_opinion"]
    issues = []
    for image in ds.image_files():
        stem = image.stem
        image_preds = preds.get(stem)
        label_lines = ds.read_label_lines(stem)
        size = ds.image_size(stem)
        if image_preds is None or label_lines is None or size is None:
            continue

        image_width, image_height = size
        labels = []
        for line_no, text in label_lines:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError):
                continue
            if 0 <= class_id < len(ds.classes):
                labels.append((line_no, class_id, (cx, cy, width, height)))

        selected_preds = []
        false_positive_preds = []
        for row in image_preds:
            class_id, conf, cx, cy, width, height = row
            box = (cx, cy, width, height)
            if conf >= rules["fp_conf"]:
                false_positive_preds.append(box)
            if (conf >= rules["conf"]
                    and width * image_width * height * image_height >= rules["min_area_px"]):
                selected_preds.append((class_id, conf, box))

        for class_id, conf, pred_box in selected_preds:
            overlaps = [
                (label_class, iou_xywh(pred_box, label_box))
                for _, label_class, label_box in labels
            ]
            candidates = [(label_class, iou) for label_class, iou in overlaps if iou >= rules["iou_missing"]]

            if not candidates:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_MISSING", stem,
                    "model thấy vật chưa có box nhãn tương ứng",
                    extra={"conf": conf},
                ))
                continue

            same_class = [iou for label_class, iou in candidates if label_class == class_id]
            if same_class:
                best_iou = max(same_class)
                if best_iou < rules["iou_loose"]:
                    issues.append(Issue(
                        "second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                        "box nhãn cùng lớp có thể bị lệch hoặc quá lỏng",
                        extra={"conf": conf, "iou": best_iou},
                    ))
                continue

            best_other_iou = max(iou for _, iou in candidates)
            if best_other_iou >= rules["iou_match"]:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                    "box khớp vị trí nhưng có thể bị gán sai lớp",
                    extra={"conf": conf, "iou": best_other_iou},
                ))

        for line_no, _, label_box in labels:
            if all(iou_xywh(label_box, pred_box) < rules["iou_missing"]
                   for pred_box in false_positive_preds):
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                    "box nhãn không khớp dự đoán model nào",
                    line=line_no,
                ))

    return issues
