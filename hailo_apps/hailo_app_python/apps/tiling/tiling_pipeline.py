# region imports
# Standard library imports
from pathlib import Path
import socket
import json

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import setproctitle

# Local application-specific imports
import hailo
from hailo_apps.hailo_app_python.core.common.installation_utils import detect_hailo_arch
from hailo_apps.hailo_app_python.core.common.core import get_default_parser, get_resource_path
from hailo_apps.hailo_app_python.core.common.defines import (
    TILING_APP_TITLE, 
    TILING_POSTPROCESS_SO_FILENAME, 
    TILING_POSTPROCESS_FUNCTION,
    RESOURCES_SO_DIR_NAME,
    RESOURCES_MODELS_DIR_NAME,
    DETECTION_POSTPROCESS_SO_FILENAME,
    DETECTION_POSTPROCESS_FUNCTION,
)
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_helper_pipelines import SOURCE_PIPELINE, INFERENCE_PIPELINE, USER_CALLBACK_PIPELINE, DISPLAY_PIPELINE, TILE_CROPPER_PIPELINE, TRACKER_PIPELINE
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import GStreamerApp, app_callback_class, dummy_callback
# endregion imports

# -----------------------------------------------------------------------------------------------
# User Gstreamer Application
# -----------------------------------------------------------------------------------------------

# This class inherits from the hailo_rpi_common.GStreamerApp class
class GStreamerTilingApp(GStreamerApp):
    def __init__(self, app_callback, user_data, parser=None):
        if parser == None:
            parser = get_default_parser()
        parser.add_argument("--tiles_along_x_axis", default=3, help="Set number of tiles along x axis (columns). Default is 3")
        parser.add_argument("--tiles_along_y_axis", default=2, help="Set number of tiles along y axis (rows). Default is 2")
        parser.add_argument("--overlap_x_axis", default=0.2, help="Set overlap in percentage between tiles along x axis (columns). Default is 0.1 (10%%)")
        parser.add_argument("--overlap_y_axis", default=0.2, help="Set overlap in percentage between tiles along y axis (rows). Default is 0.1 (10%%)")
        parser.add_argument("--iou_threshold", default=0.5, help="Set iou threshold for NMS. Default is 0.5")
        parser.add_argument("--border_threshold", default=0.0, help="Set border threshold to Remove tile's exceeded objects. Relevant only for multi scaling. Default is 0.0")
        parser.add_argument("--multi_scaling", action="store_true", help="Enable multi-scaling mode for better accuracy (slower). Default is single-scale mode (faster).")
        parser.add_argument("--scale_level", default=0, help="set scales (layers of tiles) in addition to the main layer [0,1,2,3]. 0: single scale (default), 1: {(1x1)}, 2: {(1x1), (2x2)}, 3: {(1x1), (2x2), (3x3)}. Default is 0.")
        parser.add_argument("--post-process-so", default=None, help="Path to post-processing .so file. If not specified, uses default MobileNet SSD post-process.")
        parser.add_argument("--post-function", default=None, help="Post-processing function name. Common values: 'filter', 'filter_letterbox', 'mobilenet_ssd'. Default depends on post-process-so.")
        parser.add_argument("--labels-json", default=None, help="Path to custom labels JSON file to filter/rename classes.")
        parser.add_argument("--class-filter", default=None, help="Comma-separated list of class names to keep (e.g., 'hornet,bee'). All other classes will be filtered out.")
        parser.add_argument("--video-width", type=int, default=1280, help="Video width in pixels. Default is 1280")
        parser.add_argument("--video-height", type=int, default=720, help="Video height in pixels. Default is 720")
        parser.add_argument("--enable-tracking", action="store_true", help="Enable object tracking to assign unique IDs to each detected object.")
        parser.add_argument("--targeting-port", type=int, default=None, help="UDP port to send targeting coordinates to external script (e.g., 5000)")
        
        # Call the parent class constructor
        super().__init__(parser, user_data)
        
        # Override video resolution if specified
        if self.options_menu.video_width:
            self.video_width = self.options_menu.video_width
        if self.options_menu.video_height:
            self.video_height = self.options_menu.video_height
        
        print(f"Video resolution: {self.video_width}×{self.video_height}")
        
        # Handle multi_scaling flag
        if self.options_menu.multi_scaling:
            if self.options_menu.scale_level == 0:
                self.options_menu.scale_level = 2  # Default multi-scale level
            if self.options_menu.border_threshold == 0.0:
                self.options_menu.border_threshold = 0.1  # Enable border threshold for multi-scale
        else:
            # Single scaling mode (default)
            self.options_menu.scale_level = 0
            self.options_menu.border_threshold = 0.0

        # Determine the architecture if not specified
        if self.options_menu.arch is None:
            detected_arch = detect_hailo_arch()
            if detected_arch is None:
                raise ValueError("Could not auto-detect Hailo architecture. Please specify --arch manually.")
            self.arch = detected_arch
            print(f"Auto-detected Hailo architecture: {self.arch}")
        else:
            self.arch = self.options_menu.arch

        # Get HEF path from command line or use default resource path
        if self.options_menu.hef_path is not None:
            self.hef_path = self.options_menu.hef_path
        else:
            # Try to get the model from resources, fallback to a sensible default
            self.hef_path = get_resource_path(
                pipeline_name=None, 
                resource_type=RESOURCES_MODELS_DIR_NAME, 
                model='ssd_mobilenet_v1'
            )
            if self.hef_path is None:
                # Fallback to detection model if tiling model not available
                self.hef_path = get_resource_path(
                    pipeline_name='detection',
                    resource_type=RESOURCES_MODELS_DIR_NAME
                )
        
        # Get post-processing library - use YOLO post-process by default for better detection
        # You can override this with command-line arguments if needed
        if hasattr(self.options_menu, 'post_process_so') and self.options_menu.post_process_so:
            self.post_process_so = self.options_menu.post_process_so
        else:
            # Default path for YOLO post-processing
            default_yolo_path = "/usr/local/hailo/resources/so/libyolo_hailortpp_postprocess.so"
            
            # Check if default path exists
            from pathlib import Path
            if Path(default_yolo_path).exists():
                self.post_process_so = default_yolo_path
            else:
                # Try to find it via get_resource_path
                self.post_process_so = get_resource_path(
                    pipeline_name=None, 
                    resource_type=RESOURCES_SO_DIR_NAME, 
                    model=DETECTION_POSTPROCESS_SO_FILENAME
                )
                # Fallback to MobileNet SSD if YOLO not available
                if self.post_process_so is None:
                    self.post_process_so = get_resource_path(
                        pipeline_name=None, 
                        resource_type=RESOURCES_SO_DIR_NAME, 
                        model=TILING_POSTPROCESS_SO_FILENAME
                    )
        
        if hasattr(self.options_menu, 'post_function') and self.options_menu.post_function:
            self.post_function = self.options_menu.post_function
        else:
            # Use 'filter' for tiling (no letterbox needed on tiles)
            # Tiles are already cropped and resized without padding
            self.post_function = "filter"
        
        # Set default NMS thresholds for post-processing
        self.nms_score_threshold = 0.3  # Minimum confidence score
        self.nms_iou_threshold = 0.45   # IoU threshold for NMS
        self.thresholds_str = (
            f"nms-score-threshold={self.nms_score_threshold} "
            f"nms-iou-threshold={self.nms_iou_threshold} "
            f"output-format-type=HAILO_FORMAT_TYPE_FLOAT32"
        )
        
        # Set batch_size to match number of tiles for optimal performance
        # With 3x2 tiles = 6 tiles, batch_size=6 allows processing all tiles in one batch
        self.batch_size = self.options_menu.tiles_along_x_axis * self.options_menu.tiles_along_y_axis
        print(f"Batch size set to {self.batch_size} (matches {self.options_menu.tiles_along_x_axis}×{self.options_menu.tiles_along_y_axis} tiles)")
        
        # Parse class filter if provided
        self.class_filter = None
        if self.options_menu.class_filter:
            self.class_filter = set(cls.strip() for cls in self.options_menu.class_filter.split(','))
            print(f"Class filter enabled: {self.class_filter}")
            # Pass class filter to user_data for use in callback
            user_data.class_filter = self.class_filter
        
        # Setup UDP socket for targeting system if port specified
        if self.options_menu.targeting_port:
            try:
                user_data.targeting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                user_data.targeting_port = self.options_menu.targeting_port
                user_data.video_width = self.video_width
                user_data.video_height = self.video_height
                print(f"🎯 Targeting system enabled: sending coordinates to localhost:{self.options_menu.targeting_port}")
            except Exception as e:
                print(f"Warning: Could not create targeting socket: {e}")
                user_data.targeting_socket = None
        else:
            user_data.targeting_socket = None

        self.app_callback = app_callback
        setproctitle.setproctitle(TILING_APP_TITLE)
        self.create_pipeline()

    def get_pipeline_string(self):
        source_pipeline = SOURCE_PIPELINE(
            video_source=self.video_source,
            video_width=self.video_width, video_height=self.video_height,
            frame_rate=self.frame_rate, sync=self.sync,
            no_webcam_compression=True)
        
        detection_pipeline = INFERENCE_PIPELINE(
            hef_path=self.hef_path,
            post_process_so=self.post_process_so,
            post_function_name=self.post_function,
            batch_size=self.batch_size,
            config_json=self.options_menu.labels_json,
            additional_params=self.thresholds_str)
        
        tile_cropper_pipeline = TILE_CROPPER_PIPELINE(
            detection_pipeline,
            name='tile_cropper_wrapper',
            internal_offset=True,
            scale_level=self.options_menu.scale_level,
            tiling_mode=1 if self.options_menu.multi_scaling else 0,
            tiles_along_x_axis=self.options_menu.tiles_along_x_axis,
            tiles_along_y_axis=self.options_menu.tiles_along_y_axis,
            overlap_x_axis=self.options_menu.overlap_x_axis,
            overlap_y_axis=self.options_menu.overlap_y_axis,
            iou_threshold=self.options_menu.iou_threshold,
            border_threshold=self.options_menu.border_threshold
        )

        # Add tracker if enabled
        if self.options_menu.enable_tracking:
            tracker_pipeline = TRACKER_PIPELINE(class_id=-1)  # -1 = track all classes
            user_callback_pipeline = USER_CALLBACK_PIPELINE()
            display_pipeline = DISPLAY_PIPELINE(video_sink=self.video_sink, sync=self.sync, show_fps=self.show_fps)
            
            pipeline_string = (
                f'{source_pipeline} ! '
                f'{tile_cropper_pipeline} ! '
                f'{tracker_pipeline} ! '
                f'{user_callback_pipeline} ! '
                f'{display_pipeline}'
            )
        else:
            user_callback_pipeline = USER_CALLBACK_PIPELINE()
            display_pipeline = DISPLAY_PIPELINE(video_sink=self.video_sink, sync=self.sync, show_fps=self.show_fps)
            
            pipeline_string = (
                f'{source_pipeline} ! '
                f'{tile_cropper_pipeline} ! '
                f'{user_callback_pipeline} ! '
                f'{display_pipeline}'
            )

        print(pipeline_string)
        return pipeline_string
    
def app_callback(pad, info, user_data):
    """Custom callback to process and filter detections from tiled inference."""
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK
    
    # Get class filter from user_data if available
    class_filter = getattr(user_data, 'class_filter', None)
    
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    # Filter and display detections
    detections_to_remove = []
    for detection in detections:
        label = detection.get_label()
        
        # Filter if needed
        if class_filter and label not in class_filter:
            detections_to_remove.append(detection)
            continue
        
        # Display detection info
        confidence = detection.get_confidence()
        bbox = detection.get_bbox()
        
        # Get video resolution from user_data
        video_width = getattr(user_data, 'video_width', 1280)
        video_height = getattr(user_data, 'video_height', 720)
        
        # Convert normalized coordinates (0-1) to pixel coordinates
        # BBox coordinates are normalized, multiply by resolution
        bbox_xmin_px = bbox.xmin() * video_width
        bbox_ymin_px = bbox.ymin() * video_height
        bbox_width_px = bbox.width() * video_width
        bbox_height_px = bbox.height() * video_height
        
        # Calculate center coordinates in pixels
        center_x = bbox_xmin_px + (bbox_width_px / 2)
        center_y = bbox_ymin_px + (bbox_height_px / 2)
        
        # Get tracking ID if available
        unique_ids = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
        track_id = unique_ids[0].get_id() if unique_ids else None
        
        # Send to external targeting system via UDP if enabled
        targeting_socket = getattr(user_data, 'targeting_socket', None)
        if targeting_socket:
            target_data = {
                "label": label,
                "track_id": track_id,
                "center_x": round(center_x, 1),
                "center_y": round(center_y, 1),
                "confidence": round(confidence, 2),
                "width": round(bbox_width_px, 1),
                "height": round(bbox_height_px, 1),
                "resolution_width": video_width,
                "resolution_height": video_height
            }
            try:
                # Add newline for easier parsing
                message = (json.dumps(target_data) + '\n').encode('utf-8')
                targeting_socket.sendto(message, ('localhost', user_data.targeting_port))
            except Exception as e:
                pass  # Silently ignore send errors
    
    # Remove unwanted detections from ROI
    for detection in detections_to_remove:
        roi.remove_object(detection)
    
    return Gst.PadProbeReturn.OK

def main():
    # Create an instance of the user app callback class
    user_data = app_callback_class()
    # Use the custom callback to process tiled detections
    app = GStreamerTilingApp(app_callback, user_data)
    app.run()

if __name__ == "__main__":
    print("Starting Hailo Tiling App...")
    main()
