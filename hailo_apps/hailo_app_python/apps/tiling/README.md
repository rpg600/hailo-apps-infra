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

#### Run with single-scale tiling:
```bash
hailo-tile --input rpi --single_scaling
```

## Command-line Arguments

- `--tiles_along_x_axis`: Number of tiles along x axis (columns). Default: 4
- `--tiles_along_y_axis`: Number of tiles along y axis (rows). Default: 3
- `--overlap_x_axis`: Overlap percentage between tiles along x axis. Default: 0.1
- `--overlap_y_axis`: Overlap percentage between tiles along y axis. Default: 0.08
- `--iou_threshold`: IoU threshold for NMS aggregation. Default: 0.3
- `--border_threshold`: Border threshold to remove tile's exceeded objects. Default: 0.1
- `--single_scaling`: Use single scaling instead of multi-scaling. Default: False
- `--scale_level`: Number of scale layers [0-3]. Default: 2. For single scaling, must be 0.

## How It Works

1. **Tile Cropping**: The input frame is divided into overlapping tiles based on the specified parameters
2. **Detection**: Each tile is processed through the detection pipeline
3. **Aggregation**: Detections from all tiles are combined using NMS to remove duplicates
4. **Output**: The final frame contains all unique detections from all tiles

## Notes

- Multi-scale tiling processes the image at multiple resolutions for better small object detection
- Single-scale tiling is faster but may miss very small objects
- Increase overlap to reduce the chance of missing objects at tile boundaries
- The application uses SSD MobileNet V1 model optimized for tiling

To close the application, press Ctrl+C.

