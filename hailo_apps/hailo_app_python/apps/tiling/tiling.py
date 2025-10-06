# region imports
# Standard library imports

# Third-party imports
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# Local application-specific imports
import hailo
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.hailo_app_python.apps.tiling.tiling_pipeline import GStreamerTilingApp
# endregion imports

# User-defined class to be used in the callback function: Inheritance from the app_callback_class
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()

# User-defined callback function with class filtering support
def app_callback(pad, info, user_data):
    user_data.increment()  # Using the user_data to count the number of frames
    string_to_print = f"Frame count: {user_data.get_count()}\n"
    buffer = info.get_buffer()  # Get the GstBuffer from the probe info
    if buffer is None:  # Check if the buffer is valid
        return Gst.PadProbeReturn.OK
    
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    # Get class filter from user_data if available
    class_filter = getattr(user_data, 'class_filter', None)
    
    # Process detections from tiled inference
    filtered_count = 0
    for detection in detections:
        label = detection.get_label()
        
        # Apply class filter if specified
        if class_filter and label not in class_filter:
            continue  # Skip this detection
        
        filtered_count += 1
        confidence = detection.get_confidence()
        bbox = detection.get_bbox()
        string_to_print += (
            f"Detection: {label} "
            f"Confidence: {confidence:.2f} "
            f"BBox: [{bbox.xmin():.2f}, {bbox.ymin():.2f}, {bbox.width():.2f}, {bbox.height():.2f}]\n"
        )
    
    if filtered_count > 0 or user_data.get_count() % 30 == 0:  # Print every 30 frames or when detections found
        print(string_to_print)
    
    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    user_data = user_app_callback_class()  # Create an instance of the user app callback class
    app = GStreamerTilingApp(app_callback, user_data)
    app.run()
