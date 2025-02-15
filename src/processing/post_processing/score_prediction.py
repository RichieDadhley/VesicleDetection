import numpy as np
import zarr
import funlib.evaluate

def score_prediction(pred,
                    target, 
                    matching_score = 'overlap', 
                    mathching_threshold = 1, 
                    return_results=False):
    """
        Obtain a set of scores for a vesicle detection prediction result. The scores used 
        are: recall, precision and fscore for each possible label type, along with the 
        average across all labels. 

        Parameters
        -------------------
        pred (array):
            The prediction to be scored. 
        target (array):
            The ground truth to be marked against. 
        matching_score (str):
            The method to use to score matching of prediction and ground truth. 
            Fed into funlib.evaluate.detection_score. Options are 'overlap', 'iou'
            and 'distance'. Default is overlap.
        matching_threshold (float):
            The threshold between prediction and target that must be met to be considered
            a match. Fed into funlib.evaluate.detection_score. Default is 1.
        return_results (bool):
            Fed into funlib.evaluate.detection_score as 'return_matches'. Default false.

        Returns
        -------------------
        scores (dict):
            A dictionary containing the scores of the prediction. 
    """
    
    
    voxel_size = target.attrs['resolution']
    background_label = target.attrs['background_label']

    # Find the size difference between target and prediction
    if target.shape != pred.shape:
        border = [
                int((target.shape[0] - pred.shape[0])/2), 
                int((target.shape[1] - pred.shape[1])/2), 
                int((target.shape[2] - pred.shape[2])/2)
                ]
        # trim target to match prediction
        gt_data = target[
                        border[0]:-1*border[0],
                        border[1]:-1*border[1],
                        border[2]:-1*border[2],
                        ]
    else:
        gt_data = target[:,:,:]
    
    pred_data = pred[:,:,:]

    label_ids = np.unique(gt_data).astype(np.int32)
    scores = dict()

    precision_total = 0.0 
    recall_total = 0.0 
    fscore_total = 0.0

    # Remove background label from scoring
    if background_label is not None:
        label_ids = label_ids[label_ids != background_label]

    detection_scores = funlib.evaluate.detection_scores(
                                                        truth=gt_data, 
                                                        test=pred_data, 
                                                        label_ids=label_ids,
                                                        matching_score=matching_score,
                                                        matching_threshold=mathching_threshold,
                                                        voxel_size=voxel_size, 
                                                        return_matches=return_results
                                                        )

    for label in label_ids:

        tp = detection_scores[f'tp_{label}']
        fp = detection_scores[f'fp_{label}']
        fn = detection_scores[f'fn_{label}']

        num_predicted = tp + fp 
        num_relevant = tp + fn

        if num_predicted > 0:
            precision = tp/num_predicted
        else:
            precision = np.nan 

        if num_relevant > 0:
            recall = tp/num_relevant
        else: 
            recall = np.nan 

        if precision + recall > 0:
            fscore = 2*(precision * recall)/(precision + recall)
        else:
            fscore = np.nan

        # Store scores for individual label
        scores[f'precision_{label}'] = precision
        scores[f'recall_{label}'] = recall
        scores[f'fscore_{label}'] = fscore 

        # Update total scores
        precision_total += precision
        recall_total += recall 
        fscore_total += fscore

    if label_ids.size >= 1:
        scores['precision_average'] = precision_total/label_ids.size
        scores['recall_average'] = recall_total/label_ids.size
        scores['fscore_average'] = fscore_total/label_ids.size

    return scores 


if __name__ == "__main__":

    data_path = input("Provide the path to the data: ")
    pred_name = input("Provide prediction name: ")

    f = zarr.open(data_path, mode = 'r')

    target = f['target']
    pred = f[f'Predictions/{pred_name}/Hough_transformed']

    scores = score_prediction(target=target, pred=pred)

    print(scores)