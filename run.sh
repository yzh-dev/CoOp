# zeroshot
#python3  train.py --root ../../data --trainer ZeroshotCLIP --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50.yaml  --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/ --eval-only

# fewshot
# cmd1 = "python train.py --root D:\ML\Dataset --trainer CoOp --dataset-config-file configs/datasets/food101.yaml --config-file configs/trainers/CoOp/rn50.yaml --output-dir output/CoOp/ DATASET.NUM_SHOTS 8 "
#-----------------------------officehome
#python3 train.py --resume 0 --root ../../data --trainer CLIP_Adapter --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/exp1  DATASET.NUM_SHOTS 16
#python3 train.py --resume 0 --root ../../data --trainer CLIP_Adapter --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/exp1  DATASET.NUM_SHOTS 8
#------------------------- --food101
#python3 train.py --resume 0 --root ../../data --trainer CLIP_Adapter --dataset-config-file configs/datasets/food101.yaml --config-file configs/trainers/CoOp/rn50_ep50.yaml --output-dir output/CoOp/exp1  DATASET.NUM_SHOTS 16


# prompt_learner
#python3 train.py --resume 0 --root ../../data --trainer CLIP_Adapter --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/exp1

#EnCoOp
python3 train.py --resume 0 --root ../../data --trainer EnCoOp --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/EnCoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/EnCoOp/exp1
python3 train.py --resume 0 --root ../../data --trainer EnCoOp --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/EnCoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/EnCoOp/exp1
python3 train.py --resume 0 --root ../../data --trainer EnCoOp --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/EnCoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/EnCoOp/exp1
python3 train.py --resume 0 --root ../../data --trainer EnCoOp --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/EnCoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/EnCoOp/exp1
python3 train.py --resume 0 --root ../../data --trainer EnCoOp --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/EnCoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/EnCoOp/exp1

# test on the last epoch
# cmd1 = "python train.py --root D:\ML\Dataset --trainer CoOp --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50.yaml --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/exp1 "
