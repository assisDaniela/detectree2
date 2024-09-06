"""Post process predictions

These functions are used to post-process predictions from detectree2 model
"""
from pathlib import Path
import concurrent.futures
import os
import rasterio
import pycocotools.mask as mask_util
import json
from outputs import filename_geoinfo, box_filter, polygon_from_mask
import numpy as np

def project_to_geojson(tiles_path, pred_folder, output_folder, multi_class, max_workers=32):
    """Projects json predictions back in geographic space.

    Takes a json and changes it to a geojson so it can overlay with orthomosaic. Another copy is produced to overlay
    with PNGs.

    Args:
        tiles_path (str): Path to the tiles folder.
        pred_folder (str): Path to the predictions folder.
        output_fold (str): Path to the output folder.
        multi_class (bool): Whether to use multi-class predictions or not.
        max_workers (int): Number of workers to use for parallel processing. Default is 32. Use 1 for no sequential processing

    Returns:
        None
    """
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    entries = list(Path(pred_folder) / file for file in os.listdir(pred_folder) if Path(file).suffix == ".json")

    if max_workers == 1:
        print(f"Projecting {len(entries)} files")
        project_files(entries, tiles_path, output_folder, multi_class, follow=True)
        return

    max_workers = min(max_workers, len(entries))

    chunk_filenames = [ [] for i in range(max_workers) ]
    for i, entry in enumerate(entries):
        chunk_filenames[i % max_workers].append(entry)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    future = [ pool.submit(project_files, chunk, tiles_path, output_folder, multi_class) for chunk in chunk_filenames if len(chunk) > 0 ]
    pool.shutdown(wait=True)

    for f in concurrent.futures.as_completed(future):
        try:
            f.result()
        except Exception as e:
            print(e)

def stitch_crowns():
    pass

def clean_crowns():
    pass

# Auxiliary functions
def project_files(list_files, tiles_path, output_folder, multi_class, confidence=None, follow=False):
    total_files = len(list_files)
    for idx, filename in enumerate(list_files, start=1):
        if idx % 50 == 0 and follow:
            print(f"Projecting file {idx} of {total_files}: {filename}")

        tifpath = Path(tiles_path) / Path(filename.name.replace("Prediction_", "")).with_suffix(".tif")

        data = rasterio.open(tifpath)
        filename_geo = tifpath.replace('.tif', '.geojson')
        _, _, _, _, epsg = filename_geoinfo(filename_geo)

        raster_transform = data.transform

        geofile = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:EPSG::" + str(epsg)
                },
            },
            "features": [],
        }  # type: ignore # type: GeoFile

        # load the json file we need to convert into a geojson
        with open(filename, "r") as prediction_file:
            datajson = json.load(prediction_file)

        geofile_features = process_crowns(datajson, multi_class, raster_transform, filename, confidence=confidence)

        geofile["features"] = geofile_features

        output_geo_file = os.path.join(output_folder, filename.with_suffix(".geojson").name)

        with open(output_geo_file, "w") as dest:
            json.dump(geofile, dest)

def process_crowns(crowns, multi_class, raster_transform, filename: str, shift=None, confidence=None):
    geofile_features = []

    for crown_data in crowns:
        if multi_class:
            category = crown_data["category_id"]

        crown = crown_data["segmentation"]
        confidence_score = crown_data["score"]

        if confidence != None and confidence_score < confidence:
            continue
        
        # changing the coords from RLE format so can be read as numbers, here the numbers are
        # integers so a bit of info on position is lost
        mask_of_coords = mask_util.decode(crown)
        crown_coords = polygon_from_mask(mask_of_coords)
        if crown_coords == 0:
            continue

        crown_coords_array = np.array(crown_coords).reshape(-1, 2)
        x_coords, y_coords = rasterio.transform.xy(transform=raster_transform,
                                                rows=crown_coords_array[:, 1],
                                                cols=crown_coords_array[:, 0])
        
        moved_coords = list(zip(x_coords, y_coords))

        if shift != None:
            filename_geo = filename.replace('.json', '.geojson')
            bbox = box_filter(filename_geo, shift)
            if not is_edge_crown(moved_coords, bbox):
                continue

        if multi_class:
            geofile_features.append({
                "type": "Feature",
                "properties": {
                    "Confidence_score": confidence_score,
                    "category": category,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [moved_coords],
                },
            })
        else:
            geofile_features.append({
                "type": "Feature",
                "properties": {
                    "Confidence_score": confidence_score
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [moved_coords],
                },
            })

    return geofile_features

def is_edge_crown(crown_coords, bbox):
    """Checks if a crown is touching the edge of the image.

    Args:
        crown_coords (list): List of coordinates of the crown.
        bbox (list): List of coordinates of the bounding box.

    Returns:
        bool: True if the crown is touching the edge of the image, False otherwise.
    """
    pass