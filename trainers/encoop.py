import os.path as osp

import torch
import torch.nn as nn
from torch.nn import functional as F
from torch.cuda.amp import GradScaler, autocast

from dassl.engine import TRAINER_REGISTRY, TrainerX
from dassl.metrics import compute_accuracy
from dassl.utils import load_pretrained_weights, load_checkpoint
from dassl.optim import build_optimizer, build_lr_scheduler

from clip import clip
from clip.simple_tokenizer import SimpleTokenizer as _Tokenizer

_tokenizer = _Tokenizer()


def load_clip_to_cpu(cfg):
    backbone_name = cfg.MODEL.BACKBONE.NAME
    url = clip._MODELS[backbone_name]
    model_path = clip._download(url)

    try:
        # loading JIT archive
        model = torch.jit.load(model_path, map_location="cpu").eval()
        state_dict = None

    except RuntimeError:
        state_dict = torch.load(model_path, map_location="cpu")

    model = clip.build_model(state_dict or model.state_dict())

    return model


class TextEncoder(nn.Module):
    def __init__(self, clip_model):
        super().__init__()
        self.transformer = clip_model.transformer
        self.positional_embedding = clip_model.positional_embedding
        self.ln_final = clip_model.ln_final
        self.text_projection = clip_model.text_projection
        self.dtype = clip_model.dtype

    def forward(self, prompts, tokenized_prompts):
        x = prompts + self.positional_embedding.type(self.dtype)
        x = x.permute(1, 0, 2)  # NLD -> LND
        x = self.transformer(x)
        x = x.permute(1, 0, 2)  # LND -> NLD
        x = self.ln_final(x).type(self.dtype)

        # x.shape = [batch_size, 77, transformer.width]
        # take features from the eot embedding (eot_token is the highest number in each sequence) 获取类别token对应的向量
        x = x[torch.arange(x.shape[0]), tokenized_prompts.argmax(dim=-1)] @ self.text_projection

        return x


class PromptLearner(nn.Module):
    def __init__(self, cfg, classnames, clip_model):
        super().__init__()
        self.num_source_domains = cfg["NUM_SRC_DOMAINS"]

        n_cls = len(classnames)  # cls num
        n_ctx = cfg.TRAINER.COOP.N_CTX  # contex tokens num
        ctx_init = cfg.TRAINER.COOP.CTX_INIT  # 自定义的初始化上下文
        dtype = clip_model.dtype
        ctx_dim = clip_model.ln_final.weight.shape[0]
        clip_imsize = clip_model.visual.input_resolution
        cfg_imsize = cfg.INPUT.SIZE[0]
        assert cfg_imsize == clip_imsize, f"cfg_imsize ({cfg_imsize}) must equal to clip_imsize ({clip_imsize})"

        if ctx_init:
            # use given words to initialize context vectors
            ctx_init = ctx_init.replace("_", " ")
            n_ctx = len(ctx_init.split(" "))
            prompt = clip.tokenize(ctx_init)
            with torch.no_grad():
                embedding = clip_model.token_embedding(prompt).type(dtype)
            ctx_vectors_i = embedding[0, 1: 1 + n_ctx, :]
            ctx_vectors = ctx_vectors_i.unsqueeze(0).repeat(self.num_source_domains, 1, 1)
            prompt_prefix = ctx_init

        else:
            pass
            # random initialization
            # if cfg.TRAINER.COOP.CSC:  # 学习每个类别专有的上下文
            #     print("Initializing class-specific contexts")
            #     ctx_vectors = torch.empty(n_cls, n_ctx, ctx_dim, dtype=dtype)
            # else:
            #     print("Initializing a generic context")
            #     ctx_vectors = torch.empty(n_ctx, ctx_dim, dtype=dtype)  # 初始化context vectors：n_ctx*ctx_dim
            # nn.init.normal_(ctx_vectors, std=0.02)
            # prompt_prefix = " ".join(["X"] * n_ctx)  # prompt 占位符

        print(f'Initial context: "{prompt_prefix}"')
        print(f"Number of context words (tokens): {n_ctx}")
        # ctx: (num_source_domains, n_ctx, ctx_dim)，为每个domain设计一个learnable context
        self.ctx = nn.Parameter(ctx_vectors)  # to be optimized，需要优化的上下文向量context vectors

        classnames = [name.replace("_", " ") for name in classnames]
        name_lens = [len(_tokenizer.encode(name)) for name in classnames]
        prompts = [prompt_prefix + " " + name + "." for name in classnames]

        tokenized_prompts = torch.cat([clip.tokenize(p) for p in prompts])  # 会自动添加sot_token、eot_token标志
        with torch.no_grad():
            embedding = clip_model.token_embedding(tokenized_prompts).type(dtype)

        # These token vectors will be saved when in save_model(),but they should be ignored in load_model() as we want to use
        # those computed using the current class names
        # Adds a buffer to the module. Buffers can be accessed as attributes using given names.
        self.register_buffer("token_prefix", embedding[:, :1, :])  # SOS
        self.register_buffer("token_suffix", embedding[:, 1 + n_ctx:, :])  # CLS to EOS

        self.n_cls = n_cls
        self.n_ctx = n_ctx
        self.tokenized_prompts = tokenized_prompts  # torch.Tensor
        self.name_lens = name_lens
        self.class_token_position = cfg.TRAINER.COOP.CLASS_TOKEN_POSITION  # 默认将cls token放在prompt末尾



    def forward(self, domain_i):
        # ctx: (num_domains, n_ctx, ctx_dim)
        ctx = self.ctx  # 需要优化的上下文向量context vectors
        ctx = ctx.unsqueeze(1).expand(-1, self.n_cls, -1, -1)  # 拓展为num_domains, n_cls,n_ctx,ctx_dim
        ctx_i = ctx[domain_i, :, :, :]  # 获取第i个domain的context

        prefix = self.token_prefix
        suffix = self.token_suffix

        if self.class_token_position == "end":
            prompts = torch.cat(
                [
                    prefix,  # (n_cls, 1, dim)
                    ctx_i,  # (n_cls, n_ctx, dim)
                    suffix,  # (n_cls, *, dim)
                ],
                dim=1,
            )

        elif self.class_token_position == "middle":
            pass
            # half_n_ctx = self.n_ctx // 2
            # prompts = []
            # for i in range(self.n_cls):
            #     name_len = self.name_lens[i]
            #     prefix_i = prefix[i: i + 1, :, :]
            #     class_i = suffix[i: i + 1, :name_len, :]
            #     suffix_i = suffix[i: i + 1, name_len:, :]
            #     ctx_i_half1 = ctx[i: i + 1, :half_n_ctx, :]
            #     ctx_i_half2 = ctx[i: i + 1, half_n_ctx:, :]
            #     prompt = torch.cat(
            #         [
            #             prefix_i,  # (1, 1, dim)
            #             ctx_i_half1,  # (1, n_ctx//2, dim)
            #             class_i,  # (1, name_len, dim)
            #             ctx_i_half2,  # (1, n_ctx//2, dim)
            #             suffix_i,  # (1, *, dim)
            #         ],
            #         dim=1,
            #     )
            #     prompts.append(prompt)
            # prompts = torch.cat(prompts, dim=0)

        elif self.class_token_position == "front":
            pass
            # prompts = []
            # for i in range(self.n_cls):
            #     name_len = self.name_lens[i]
            #     prefix_i = prefix[i: i + 1, :, :]
            #     class_i = suffix[i: i + 1, :name_len, :]
            #     suffix_i = suffix[i: i + 1, name_len:, :]
            #     ctx_i = ctx[i: i + 1, :, :]
            #     prompt = torch.cat(
            #         [
            #             prefix_i,  # (1, 1, dim)
            #             class_i,  # (1, name_len, dim)
            #             ctx_i,  # (1, n_ctx, dim)
            #             suffix_i,  # (1, *, dim)
            #         ],
            #         dim=1,
            #     )
            #     prompts.append(prompt)
            # prompts = torch.cat(prompts, dim=0)

        else:
            raise ValueError

        return prompts


class CustomCLIP(nn.Module):
    def __init__(self, cfg, classnames, clip_model):
        super().__init__()

        # ----------------------------------------------------
        self.prompt_learner = PromptLearner(cfg, classnames, clip_model)
        self.tokenized_prompts = self.prompt_learner.tokenized_prompts
        self.image_encoder = clip_model.visual
        self.text_encoder = TextEncoder(clip_model)
        self.logit_scale = clip_model.logit_scale
        self.dtype = clip_model.dtype
        self.split_batch = cfg["SPLIT_BATCH"]
        self.cfg = cfg

    def forward(self, image, domain):
        # 按照域划分数据
        image_list = torch.split(image, self.split_batch, 0)  # list
        domain_list = torch.split(domain, self.split_batch, 0)
        logits = []
        for imgs, domains in zip(image_list, domain_list):  # 迭代每个domain的数据
            image_features = self.image_encoder(imgs.type(self.dtype))
            prompts_i = self.prompt_learner(domains[0])  # 添加了提示词的向量 n_cls * 77 * ctx_dim

            tokenized_prompts = self.tokenized_prompts  # n_cls * 77，prompts的token
            text_features = self.text_encoder(prompts_i,
                                              tokenized_prompts)  # tokenized_prompts的作用是找到到每个类别对应的eot_token位置

            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            logit_scale = self.logit_scale.exp()
            logits_i = logit_scale * image_features @ text_features.t()
            logits.append(logits_i)
        logits =torch.cat(logits,dim=0)
        return logits

    def ensemble_inference(self, image):  # input:BCHW，取所有所有domain_specific context的平均预测结果
        logits = []
        for domain_i in range(self.cfg["NUM_SRC_DOMAINS"]):
            image_features = self.image_encoder(image.type(self.dtype))
            prompts_i = self.prompt_learner(domain_i)  # 添加了提示词的向量 n_cls * 77 * ctx_dim
            tokenized_prompts = self.tokenized_prompts  # n_cls * 77，prompts的token
            text_features = self.text_encoder(prompts_i,
                                              tokenized_prompts)  # tokenized_prompts的作用是找到到每个类别对应的eot_token位置
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            logit_scale = self.logit_scale.exp()
            logits_i = logit_scale * image_features @ text_features.t()
            logits.append(logits_i.unsqueeze(0))
        logits = torch.cat(logits, dim=0)
        logits = torch.mean(logits, dim=0)
        return logits


@TRAINER_REGISTRY.register()
class EnCoOp(TrainerX):
    """Context Optimization (CoOp).

    Learning to Prompt for Vision-Language Models
    https://arxiv.org/abs/2109.01134
    """

    def check_cfg(self, cfg):
        assert cfg.TRAINER.COOP.PREC in ["fp16", "fp32", "amp"]
        assert cfg.DATALOADER.TRAIN_X.SAMPLER == "RandomDomainSampler"
        # assert len(cfg.TRAINER.DAELDG.STRONG_TRANSFORMS) > 0

    def build_model(self):
        # ------------------通过cfg传递参数
        #     根据src_domain个数设计多个可学习的learnable context
        n_domain = self.cfg.DATALOADER.TRAIN_X.N_DOMAIN
        batch_size = self.cfg.DATALOADER.TRAIN_X.BATCH_SIZE
        if n_domain <= 0:
            n_domain = self.num_source_domains
        self.split_batch = batch_size // n_domain
        self.n_domain = n_domain
        self.cfg["NUM_SRC_DOMAINS"] = self.num_source_domains
        self.cfg["SPLIT_BATCH"] = self.split_batch

        cfg = self.cfg
        classnames = self.dm.dataset.classnames

        print(f"Loading CLIP (backbone: {cfg.MODEL.BACKBONE.NAME})")
        clip_model = load_clip_to_cpu(cfg)

        if cfg.TRAINER.COOP.PREC == "fp32" or cfg.TRAINER.COOP.PREC == "amp":
            # CLIP's default precision is fp16
            clip_model.float()

        print("Building custom CLIP")
        self.model = CustomCLIP(cfg, classnames, clip_model)

        print("Turning off gradients in both the image and the text encoder")
        for name, param in self.model.named_parameters():
            if "prompt_learner" not in name:  # 冻结视觉和文本编码器
                param.requires_grad_(False)

        if cfg.MODEL.INIT_WEIGHTS:
            load_pretrained_weights(self.model.prompt_learner, cfg.MODEL.INIT_WEIGHTS)

        self.model.to(self.device)
        # NOTE: only give prompt_learner to the optimizer
        self.optim = build_optimizer(self.model.prompt_learner, cfg.OPTIM)  # CoOp只训练prompt_learner
        self.sched = build_lr_scheduler(self.optim, cfg.OPTIM)
        self.register_model("prompt_learner", self.model.prompt_learner, self.optim, self.sched)

        self.scaler = GradScaler() if cfg.TRAINER.COOP.PREC == "amp" else None

        # Note that multi-gpu training could be slow because CLIP's size is
        # big, which slows down the copy operation in DataParallel
        device_count = torch.cuda.device_count()
        if device_count > 1:
            print(f"Multiple GPUs detected (n_gpus={device_count}), use all of them!")
            self.model = nn.DataParallel(self.model)

    def forward_backward(self, batch):
        image, label, domain = self.parse_batch_train(batch)

        prec = self.cfg.TRAINER.COOP.PREC
        if prec == "amp":
            with autocast():
                output = self.model(image)
                loss = F.cross_entropy(output, label)
            self.optim.zero_grad()
            self.scaler.scale(loss).backward()
            self.scaler.step(self.optim)
            self.scaler.update()
        else:
            output = self.model(image, domain)
            loss = F.cross_entropy(output, label)
            self.model_backward_and_update(loss)

        loss_summary = {
            "loss": loss.item(),
            "acc": compute_accuracy(output, label)[0].item(),
        }

        if (self.batch_idx + 1) == self.num_batches:
            self.update_lr()

        return loss_summary

    def parse_batch_train(self, batch):
        input = batch["img"]
        label = batch["label"]
        domain = batch["domain"]
        input = input.to(self.device)
        label = label.to(self.device)
        domain = domain.to(self.device)
        return input, label, domain

    def load_model(self, directory, epoch=None):
        if not directory:
            print("Note that load_model() is skipped as no pretrained model is given")
            return

        names = self.get_model_names()

        # By default, the best model is loaded
        model_file = "model-best.pth.tar"

        if epoch is not None:
            model_file = "model.pth.tar-" + str(epoch)

        for name in names:
            model_path = osp.join(directory, name, model_file)

            if not osp.exists(model_path):
                raise FileNotFoundError('Model not found at "{}"'.format(model_path))

            checkpoint = load_checkpoint(model_path)
            state_dict = checkpoint["state_dict"]
            epoch = checkpoint["epoch"]

            # Ignore fixed token vectors
            if "token_prefix" in state_dict:
                del state_dict["token_prefix"]

            if "token_suffix" in state_dict:
                del state_dict["token_suffix"]

            print("Loading weights to {} " 'from "{}" (epoch = {})'.format(name, model_path, epoch))
            # set strict=False
            self._models[name].load_state_dict(state_dict, strict=False)
