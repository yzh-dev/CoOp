import os

# zeroshot
# cmd1 = "python train.py --root D:\ML\Dataset --trainer ZeroshotCLIP --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50.yaml  --output-dir output/CoOp/ --eval-only --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/ --eval-only"

# fewshot
# cmd1 = "python train.py --root D:\ML\Dataset --trainer CoOp --dataset-config-file configs/datasets/food101.yaml --config-file configs/trainers/CoOp/rn50.yaml --output-dir output/CoOp/ DATASET.NUM_SHOTS 8 "


# prompt_learner
cmd1 = "python3 train.py --resume 0 --root ../../data --trainer CLIP_Adapter --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/exp1 "
cmd2 = "python3 train.py --resume 0 --root ../../data --trainer CLIP_Adapter --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50_ep50_ctxv1.yaml --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/exp1 "


# test on the last epoch
# cmd1 = "python train.py --root D:\ML\Dataset --trainer CoOp --dataset-config-file configs/datasets/officehome.yaml --config-file configs/trainers/CoOp/rn50.yaml --source-domains art product real_world --target-domains clipart --output-dir output/CoOp/exp1 "


os.system(cmd1)
os.system(cmd2)
# os.system(cmd3)
# os.system(cmd4)
# os.system(cmd5)
