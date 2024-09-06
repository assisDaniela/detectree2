"""Post process predictions

These functions are used to post-process predictions from detectree2 model
"""
from pathlib import Path
import concurrent.futures
import os


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
def project_files(entries, tiles_path, output_folder, multi_class, confidence=None, follow=False):
    pass