# Tiling Application

The tiling application divides input frames into smaller tiles for processing, enabling detection of small objects in high-resolution images. This technique improves detection accuracy by processing the image at multiple scales.

## Features

- **Multi-scale tiling**: Process images at different tile scales for improved detection
- **Single-scale tiling**: Process images with uniform tile size
- **Configurable overlap**: Set overlap between tiles to avoid missing objects at tile boundaries
- **NMS aggregation**: Combine detections from multiple tiles using Non-Maximum Suppression (NMS)
- **Border threshold**: Remove detections near tile borders to reduce false positives

## Usage

#### Run with video file:
```bash
hailo-tile --input /path/to/video.mp4
```

#### Run with Raspberry Pi camera (recommended):
```bash
hailo-tile --input rpi
```

#### Run with libcamera:
```bash
hailo-tile --input libcamera
```

#### Run with USB camera:
```bash
hailo-tile --input usb
# or specify device directly
hailo-tile --input /dev/video0
```

#### Run with RTSP stream:
```bash
hailo-tile --input rtsp://username:password@ip_address:port/path
```

#### Run with custom tiling parameters:
```bash
hailo-tile --input rpi \
  --tiles_along_x_axis 4 \
  --tiles_along_y_axis 3 \
  --overlap_x_axis 0.1 \
  --overlap_y_axis 0.08 \
  --iou_threshold 0.3
```

#### Run with multi-scale tiling (slower but more accurate):
```bash
hailo-tile --input rpi --multi_scaling --scale_level 2
```

#### Run with more tiles for better small object detection:
```bash
hailo-tile --input rpi \
  --tiles_along_x_axis 4 \
  --tiles_along_y_axis 3 \
  --overlap_x_axis 0.1 \
  --overlap_y_axis 0.1
```

## Command-line Arguments

### Tiling Parameters (Optimized for Performance)
- `--tiles_along_x_axis`: Number of tiles along x axis (columns). **Default: 3** (6 tiles total = fast)
- `--tiles_along_y_axis`: Number of tiles along y axis (rows). **Default: 2**
- `--overlap_x_axis`: Overlap percentage between tiles along x axis. **Default: 0.0** (no overlap = faster)
- `--overlap_y_axis`: Overlap percentage between tiles along y axis. **Default: 0.0**
- `--iou_threshold`: IoU threshold for NMS aggregation. Default: 0.3
- `--border_threshold`: Border threshold to remove tile's exceeded objects. **Default: 0.0** (auto-set to 0.1 with multi-scaling)
- `--multi_scaling`: Enable multi-scaling mode for better accuracy (slower, ~2-5 FPS on RPi). **Default: disabled** (single-scale mode is faster, ~10-15 FPS)
- `--scale_level`: Number of scale layers [0-3]. **Default: 0** (single scale). Auto-set to 2 when using --multi_scaling

### Model Parameters
- `--hef-path`: Path to your custom .hef model file
- `--post-process-so`: Path to post-processing .so file (optional, defaults to YOLO post-process)
- `--post-function`: Post-processing function name (optional, defaults to `filter`)

### Default Post-Processing Parameters
The application uses these optimized defaults for YOLO models:
- **NMS Score Threshold**: 0.3 (minimum confidence to keep a detection)
- **NMS IoU Threshold**: 0.45 (overlap threshold for duplicate removal)
- **Output Format**: FLOAT32

## How It Works

1. **Tile Cropping**: The input frame is divided into overlapping tiles based on the specified parameters
2. **Detection**: Each tile is processed through the detection pipeline
3. **Aggregation**: Detections from all tiles are combined using NMS to remove duplicates
4. **Output**: The final frame contains all unique detections from all tiles

## Using Your Own Model

You can use your custom `.hef` model with the tiling application:

### Basic usage with custom model:
```bash
hailo-tile --input rpi \
  --hef-path /path/to/your/model.hef
```

### For YOLO models (recommended for object detection):
```bash
# YOLO with standard post-processing
hailo-tile --input rpi \
  --hef-path /path/to/yolov8_hornet.hef \
  --post-process-so /usr/lib/hailo-post-processes/libyolo_hailortpp_postprocess.so \
  --post-function filter

# YOLO with letterbox post-processing (if your model uses letterbox)
hailo-tile --input rpi \
  --hef-path /path/to/yolov8_hornet.hef \
  --post-process-so /usr/lib/hailo-post-processes/libyolo_hailortpp_postprocess.so \
  --post-function filter_letterbox
```

### Complete example for hornet detection:
```bash
hailo-tile --input rpi \
  --hef-path /home/pi/models/yolov8n_hornet_640.hef \
  --post-process-so /usr/lib/hailo-post-processes/libyolo_hailortpp_postprocess.so \
  --post-function filter \
  --tiles_along_x_axis 6 \
  --tiles_along_y_axis 4 \
  --overlap_x_axis 0.15 \
  --overlap_y_axis 0.15 \
  --scale_level 2
```

### Available post-processing libraries:
- **YOLO**: `libyolo_hailortpp_postprocess.so` (functions: `filter`, `filter_letterbox`)
- **MobileNet SSD**: `libmobilenet_ssd_postprocess.so` (function: `mobilenet_ssd`)
- **YOLOv5 Segmentation**: `libyolov5seg_postprocess.so` (function: `filter_letterbox`)
- **YOLOv8 Pose**: `libyolov8pose_postprocess.so` (function: `filter_letterbox`)

## Notes

- Multi-scale tiling processes the image at multiple resolutions for better small object detection
- Single-scale tiling is faster but may miss very small objects
- Increase overlap to reduce the chance of missing objects at tile boundaries
- The default model is SSD MobileNet V1, but you can use any compatible .hef model
- For best results with small objects (like hornets), use higher resolution and more tiles

To close the application, press Ctrl+C.

