def image_bbox_to_excalidraw(
    bbox: list[float],
    image_element: dict,
    original_width: int,
    original_height: int,
    padding_ratio: float = 0.12,
) -> dict:
    """
    Convert a bounding box from original image pixel
    coordinates into Excalidraw scene coordinates.

    Current version supports:
    - scale [1, 1]
    - angle 0
    - no crop
    """

    x1, y1, x2, y2 = bbox

    image_x = image_element["x"]
    image_y = image_element["y"]

    element_width = image_element["width"]
    element_height = image_element["height"]

    scale_x = (
        element_width / original_width
    )

    scale_y = (
        element_height / original_height
    )

    canvas_x1 = (
        image_x + x1 * scale_x
    )

    canvas_y1 = (
        image_y + y1 * scale_y
    )

    canvas_x2 = (
        image_x + x2 * scale_x
    )

    canvas_y2 = (
        image_y + y2 * scale_y
    )

    width = canvas_x2 - canvas_x1
    height = canvas_y2 - canvas_y1

    # Add some space around the detected object
    # so the ellipse does not touch the face.
    padding_x = width * padding_ratio
    padding_y = height * padding_ratio

    return {
        "x": canvas_x1 - padding_x,
        "y": canvas_y1 - padding_y,
        "width": width + 2 * padding_x,
        "height": height + 2 * padding_y,
    }