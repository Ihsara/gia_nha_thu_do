import fiona
import zipfile
import os
import tempfile

# --- Configuration ---
TOPOGRAPHY_ZIP_PATH = os.path.join('data', 'open', 'L4134C.zip')

zip_exists = os.path.exists(TOPOGRAPHY_ZIP_PATH)

if not zip_exists:
    print(f"Zip File Not Found. Could not find the zip file at {os.path.abspath(TOPOGRAPHY_ZIP_PATH)}.")
else:
    print(f"Zip File Found. Located at {os.path.abspath(TOPOGRAPHY_ZIP_PATH)}.")

if zip_exists:
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(TOPOGRAPHY_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        gml_path = None
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.gml'):
                    gml_path = os.path.join(root, file)
                    break
            if gml_path:
                break
        
        if not gml_path:
            print("GML File Not Found. Could not find a GML file in the extracted archive.")
        else:
            print(f"GML File Found. Located at {gml_path}.")
            
            try:
                with fiona.open(gml_path, 'r') as source:
                    print("**Schema:**")
                    print(source.schema)
                    
                    # Print the first feature to inspect its geometry
                    first_feature = next(iter(source))
                    print("**First Feature:**")
                    print(first_feature)
            except Exception as e:
                print(f"Error inspecting GML file: {e}")
