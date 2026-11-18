"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line


def fix(ds, issues, cfg):
    errors = [issue for issue in issues if issue.severity == ERROR]
    fixes = []
    removed_images = set()
    remove_order = []
    drop_lines = defaultdict(dict)
    clip_lines = defaultdict(dict)
    needs_label = []
    rename_classes = False

    for issue in errors:
        if issue.code.startswith("DUP_IMAGE_") or issue.code in {
            "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE",
        }:
            if issue.image not in removed_images:
                removed_images.add(issue.image)
                remove_order.append(issue.image)
        elif issue.code == "BAD_CLASS_NAME":
            rename_classes = True
        elif issue.code == "MISSING_LABEL_FILE":
            needs_label.append(issue)
        elif issue.code in {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}:
            if issue.line is not None:
                drop_lines[issue.image].setdefault(issue.line, issue)
        elif issue.code == "BOX_OUT_OF_IMAGE":
            if issue.line is not None:
                clip_lines[issue.image].setdefault(issue.line, issue)

    for stem in remove_order:
        image_paths = [path for path in ds.image_files() if path.stem == stem]
        label_path = ds.label_path(stem)
        if not image_paths and not label_path.exists():
            continue
        for path in image_paths:
            path.unlink()
        if label_path.exists():
            label_path.unlink()
        fixes.append({
            "image": stem,
            "line": None,
            "action": "remove_image",
            "before": ", ".join(path.name for path in image_paths),
            "after": "",
        })

    if rename_classes:
        yaml_path = ds.yaml_path
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) if yaml_path.exists() else {}
        data = data or {}
        existing_names = data.get("names", {})
        if isinstance(existing_names, dict):
            current_names = [existing_names[key] for key in sorted(existing_names, key=int)]
        else:
            current_names = existing_names
        target_names = cfg["classes"]
        if current_names != target_names:
            data["names"] = target_names
            yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
            fixes.append({
                "image": "data.yaml",
                "line": None,
                "action": "rename_classes",
                "before": str(current_names),
                "after": str(target_names),
            })

    for issue in needs_label:
        if issue.image not in removed_images:
            fixes.append({
                "image": issue.image,
                "line": None,
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    for stem in sorted(set(drop_lines) | set(clip_lines)):
        if stem in removed_images:
            continue
        label_path = ds.label_path(stem)
        if not label_path.exists():
            continue
        original_text = label_path.read_text(encoding="utf-8", errors="replace")
        lines = original_text.splitlines()
        changed = False
        for line_no in sorted(set(drop_lines[stem]) | set(clip_lines[stem])):
            if line_no < 1 or line_no > len(lines):
                continue
            before = lines[line_no - 1]
            if line_no in drop_lines[stem]:
                lines[line_no - 1] = None
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": before,
                    "after": "",
                })
                changed = True
                continue

            try:
                class_id, cx, cy, width, height = parse_yolo_line(before)
            except (ValueError, OverflowError):
                lines[line_no - 1] = None
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": before,
                    "after": "",
                })
                changed = True
                continue

            left = max(0.0, cx - width / 2)
            top = max(0.0, cy - height / 2)
            right = min(1.0, cx + width / 2)
            bottom = min(1.0, cy + height / 2)
            if right <= left or bottom <= top:
                lines[line_no - 1] = None
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": before,
                    "after": "",
                })
            else:
                after = (
                    f"{class_id} {(left + right) / 2:.10g} {(top + bottom) / 2:.10g} "
                    f"{right - left:.10g} {bottom - top:.10g}"
                )
                lines[line_no - 1] = after
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "clip_box",
                    "before": before,
                    "after": after,
                })
            changed = True

        if changed:
            trailing_newline = original_text.endswith(("\n", "\r"))
            output = "\n".join(line for line in lines if line is not None)
            if trailing_newline and output:
                output += "\n"
            label_path.write_text(output, encoding="utf-8")

    return fixes
