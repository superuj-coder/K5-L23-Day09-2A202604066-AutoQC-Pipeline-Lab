"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    rules = cfg["label_format"]
    issues = []

    for image in ds.image_files():
        stem = image.stem
        previous_boxes = []
        size = ds.image_size(stem)
        lines = ds.read_label_lines(stem)
        for line_no, text in lines or []:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except ValueError as exc:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, str(exc), line=line_no))
                continue

            if not 0 <= class_id < len(ds.classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"id lớp {class_id} ngoài phạm vi", line=line_no))
                continue

            if width <= 0 or height <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, "rộng và cao của box phải lớn hơn 0", line=line_no))
                continue

            left, top = cx - width / 2, cy - height / 2
            right, bottom = cx + width / 2, cy + height / 2
            overflow = max(0.0, -left, -top, right - 1, bottom - 1)
            if overflow > rules["overflow_tol"]:
                issues.append(Issue(
                    "label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                    f"box vượt biên ảnh {overflow:.6g}", line=line_no,
                    extra={"overflow": overflow},
                ))

            box = (cx, cy, width, height)
            if any(class_id == old_class and iou_xywh(box, old_box) > rules["dup_box_iou"]
                   for old_class, old_box in previous_boxes):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "box trùng với box cùng lớp trước đó", line=line_no))
            previous_boxes.append((class_id, box))

            if size is not None:
                image_width, image_height = size
                if min(width * image_width, height * image_height) < rules["min_box_px"]:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem, "cạnh ngắn của box nhỏ hơn ngưỡng", line=line_no))

            if width * height > rules["max_box_frac"]:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem, "diện tích box lớn hơn ngưỡng", line=line_no))

    return issues
