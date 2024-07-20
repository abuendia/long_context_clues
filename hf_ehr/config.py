import json
import os
from typing import TypedDict, Dict, Optional, List, Any, Literal, Union, Tuple
from omegaconf import DictConfig, OmegaConf
from loguru import logger
from dataclasses import dataclass, asdict, field

SPLIT_SEED: int = 97
SPLIT_TRAIN_CUTOFF: float = 70
SPLIT_VAL_CUTOFF: float = 85

H100_BASE_DIR: str = '/local-scratch/nigam/users/hf_ehr/'
A100_BASE_DIR: str = '/local-scratch/nigam/hf_ehr/'
V100_BASE_DIR: str = '/local-scratch/nigam/hf_ehr/'
GPU_BASE_DIR: str = '/home/hf_ehr/'

PATH_TO_CACHE_DIR: str = '/share/pi/nigam/mwornow/hf_ehr/cache/'
PATH_TO_TOKENIZERS_DIR: str = os.path.join(PATH_TO_CACHE_DIR, 'tokenizers/') # TODO - NEW
PATH_TO_TOKENIZER_CLMBR_v8_DIR: str = os.path.join(PATH_TO_TOKENIZERS_DIR, 'clmbr_v8/') # TODO - NEW
PATH_TO_TOKENIZER_DESC_v8_DIR: str = os.path.join(PATH_TO_TOKENIZERS_DIR, 'desc_v8/') # TODO - NEW
PATH_TO_TOKENIZER_CLMBR_v8_CONFIG: str = os.path.join(PATH_TO_TOKENIZER_CLMBR_v8_DIR, 'tokenizer_config.json') # TODO - NEW
PATH_TO_TOKENIZER_DESC_v8_CONFIG: str = os.path.join(PATH_TO_TOKENIZER_DESC_v8_DIR, 'tokenizer_config.json') # TODO - NEW

PATH_TO_TOKENIZER_v8_DIR: str = os.path.join(PATH_TO_CACHE_DIR, 'tokenizer_v8/')
PATH_TO_TOKENIZER_v8_CLMBR_DIR: str = os.path.join(PATH_TO_CACHE_DIR, 'tokenizer_v8_clmbr/')
PATH_TO_TOKENIZER_v9_DIR: str = os.path.join(PATH_TO_CACHE_DIR, 'tokenizer_v9/')
PATH_TO_TOKENIZER_v9_LITE_DIR: str = os.path.join(PATH_TO_CACHE_DIR, 'tokenizer_v9_lite/')
PATH_TO_RUNS_DIR: str = os.path.join(PATH_TO_CACHE_DIR, 'runs/')
PATH_TO_DATASET_CACHE_DIR = os.path.join(PATH_TO_CACHE_DIR, 'dataset/')
PATH_TO_FEMR_EXTRACT_v9 = '/share/pi/nigam/data/som-rit-phi-starr-prod.starr_omop_cdm5_deid_2023_08_13_extract_v9'
PATH_TO_FEMR_EXTRACT_v8 = '/share/pi/nigam/data/som-rit-phi-starr-prod.starr_omop_cdm5_deid_2023_02_08_extract_v8_no_notes'

# TODO - remove start
class Detail(TypedDict):
    token_2_count: Dict[str, int] # mapping [key] = token, [val] = count of that token
    unit_2_quartiles: Optional[List[float]] # mapping [key] = unit, [val] = list of quartiles
    is_numeric: Optional[bool] # if TRUE, then code is a lab value

class Code2Detail(TypedDict):
    """JSON file named `code_2_detail.json` which is a dict with [key] = code from FEMR, [val] = Detail dict"""
    code: Detail
# TODO - remove end

@dataclass()
class Event():
    code: str # LOINC/1234
    value: Optional[Any] = None # 123.45 or 'YES' or None
    unit: Optional[str] = None # mg/dL or None
    start: Optional[str] = None # 2023-08-13
    end: Optional[str] = None # 2023-08-13
    omop_table: Optional[str] = None  # 'measurement' or 'observation' or None
    
    def to_dict(self):
        return asdict(self)

#############################################
#
# Token Stats
#
#############################################
@dataclass()
class TCEStat():
    type: Literal['count_occurrences', 'count_patients', 'ppl'] # type of this stat

    def to_dict(self) -> dict:
        return asdict(self)
    
@dataclass()
class CountOccurrencesTCEStat(TCEStat):
    # Counts total # of occurrences of token in dataset split
    split: Optional[str] = None
    dataset: Optional[str] = None
    count: Optional[str] = None
    type: str = 'count_occurrences'

@dataclass()
class CountPatientsTCEStat(TCEStat):
    # Counts total # of unique patients with this token in dataset split
    split: Optional[str] = None
    dataset: Optional[str] = None
    count: Optional[int] = None
    type: str = 'count_patients'

@dataclass()
class PPLTCEStat(TCEStat):
    # Record the average perplexity of the token in the dataset split
    split: Optional[str] = None
    dataset: Optional[str] = None
    model: Optional[str] = None
    ppl: Optional[float] = None
    type: str = 'ppl'

#############################################
#
# Token Types
#
#############################################
@dataclass()
class TokenizerConfigEntry():
    code: str # LOINC/1234 -- raw code
    type: Literal['numerical_range', 'categorical', 'code'] # type of this token
    description: Optional[str] = None # 'Glucose' -- description of the code
    tokenization: Dict[str, Any] = field(default_factory=dict) # various info helpful for tokenizing
    stats: List[TCEStat] = field(default_factory=list) # various stats about this token

    def to_dict(self) -> dict:
        return asdict(self)

    def to_token(self):
        raise NotImplementedError("Subclasses must implement this method.")
    
    def get_stat(self, type_: str, settings: Optional[dict])-> Optional[TCEStat]:
        """Returns stat with specified type (required) and settings (optional)"""
        for s in self.stats:
            if s.type == type_:
                if settings is not None:
                    for key, val in settings.items():
                        if getattr(s, key) != val:
                            break
                return s
        return None

@dataclass()
class CodeTCE(TokenizerConfigEntry):
    type: str = 'code'

    def to_token(self) -> str:
        # LOINC/1234
        return f"{self.code}"

@dataclass()
class NumericalRangeTCE(TokenizerConfigEntry):
    type: str = 'numerical_range'
    tokenization: Dict[str, Any] = field(default_factory=lambda: {'unit' : None, 'range_start': None, 'range_end' : None, })
    
    def to_token(self)-> str:
        # LOINC/1234 || mg/dL || 0.0 - 100.0
        return f"{self.code} || {self.tokenization['unit']} || {self.tokenization['range_start']} - {self.tokenization['range_end']}"

@dataclass()
class CategoricalTCE(TokenizerConfigEntry):
    type: str = 'categorical'
    tokenization: Dict[str, Any] = field(default_factory=lambda: {'categories': [] })
    
    def to_token(self)-> str:
        # LOINC/1234 || category1,category2,category3
        return f"{self.code} || {','.join(self.tokenization['categories'])}"


#############################################
#
# Tokenizer config helpers
#
#############################################
def save_tokenizer_config_to_path(path_to_tokenizer_config: str, tokenizer_config: List[TokenizerConfigEntry], metadata: Optional[Dict] = None) -> None:
    """Given a path to a `tokenizer_config.json` file, saves the JSON config to disk."""
    json.dump({
        'metadata' : metadata if metadata else {},
        'tokens' : [ x.to_dict() for x in tokenizer_config ],
    }, open(path_to_tokenizer_config, 'w'), indent=2)

def load_tokenizer_config_from_path(path_to_tokenizer_config: str, is_return_metadata: bool = False) -> Union[List[TokenizerConfigEntry], Tuple[List[TokenizerConfigEntry], Dict[str, Any]]]:
    """Given a path to a `tokenizer_config.json` file, loads the JSON config and parses into Python objects."""
    raw_data = json.load(open(path_to_tokenizer_config, 'r'))
    raw_metadata: Dict[str, Any] = raw_data['metadata']
    raw_tokens: Dict[str, Any] = raw_data['tokens']
    
    # Parse token Dict => TokenizerConfigEntry objects
    config: List[TokenizerConfigEntry] = []
    for entry in raw_tokens:
        raw_stats = entry.pop('stats')
        stats: List[TCEStat] = []
        for stat in raw_stats:
            if stat['type'] == 'count_occurrences':
                stats.append(CountOccurrencesTCEStat(**stat))
            elif stat['type'] == 'count_patients':
                stats.append(CountPatientsTCEStat(**stat))
            elif stat['type'] == 'ppl':
                stats.append(PPLTCEStat(**stat))
            else:
                raise ValueError(f"Unknown stat type: {stat}")
        if entry['type'] == 'code':
            config.append(CodeTCE(**entry, stats=stats))
        elif entry['type'] == 'numerical_range':
            config.append(NumericalRangeTCE(**entry, stats=stats))
        elif entry['type'] == 'categorical':
            config.append(CategoricalTCE(**entry, stats=stats))
        else:
            raise ValueError(f"Unknown token type: {entry}")
    if is_return_metadata:
        return config, raw_metadata
    else:
        return config

#############################################
#
# Helper functions
#
#############################################

def copy_file(src: str, dest: str, is_overwrite_if_exists: bool = False) -> None:
    """Copy a file or directory if it does not exist."""
    if is_overwrite_if_exists or not os.path.exists(os.path.join(dest, os.path.basename(src))):
        if os.path.isdir(src):
            logger.info(f"Copying directory from `{src}` to `{dest}`.")
            os.system(f'cp -r {src} {dest}')
        else:
            logger.info(f"Copying file from `{src}` to `{dest}`.")
            os.system(f'cp {src} {dest}')

def copy_resources_to_local(base_dir: str, is_overwrite_if_exists: bool = False) -> None:
    """Copy resources to local-scratch directories."""
    os.makedirs(base_dir, exist_ok=True)
    tokenizer_v9_lite_dir = os.path.join(base_dir, 'tokenizer_v9_lite')
    tokenizer_v9_dir = os.path.join(base_dir, 'tokenizer_v9')
    tokenizer_v8_clmbr_dir = os.path.join(base_dir, 'tokenizer_v8_clmbr')
    tokenizer_v8_dir = os.path.join(base_dir, 'tokenizer_v8')
    os.makedirs(tokenizer_v9_dir, exist_ok=True)
    os.makedirs(tokenizer_v9_lite_dir, exist_ok=True)
    os.makedirs(tokenizer_v8_clmbr_dir, exist_ok=True)
    os.makedirs(tokenizer_v8_dir, exist_ok=True)
    copy_file('/share/pi/nigam/data/som-rit-phi-starr-prod.starr_omop_cdm5_deid_2023_08_13_extract_v9', base_dir, is_overwrite_if_exists=False)
    copy_file('/share/pi/nigam/data/som-rit-phi-starr-prod.starr_omop_cdm5_deid_2023_02_08_extract_v8_no_notes', base_dir, is_overwrite_if_exists=False)
    copy_file(os.path.join(PATH_TO_TOKENIZER_v9_LITE_DIR, 'code_2_detail.json'), tokenizer_v9_lite_dir, is_overwrite_if_exists)
    copy_file(os.path.join(PATH_TO_TOKENIZER_v9_DIR, 'code_2_detail.json'), tokenizer_v9_dir, is_overwrite_if_exists)
    copy_file(os.path.join(PATH_TO_TOKENIZER_v8_CLMBR_DIR, 'code_2_detail.json'), tokenizer_v8_clmbr_dir, is_overwrite_if_exists)
    copy_file(os.path.join(PATH_TO_TOKENIZER_v8_DIR, 'code_2_detail.json'), tokenizer_v8_dir, is_overwrite_if_exists)

def get_path_to_code_2_details(config: DictConfig, base_dir: str) -> str:
    """Get the path to code_2_detail.json."""
    path_to_code_2_detail: str = ''
    if "tokenizer_v9_lite" in config.data.tokenizer.path_to_code_2_detail:
        path_to_code_2_detail = config.data.tokenizer.path_to_code_2_detail.replace('/share/pi/nigam/mwornow/hf_ehr/cache/tokenizer_v9_lite/', f"{os.path.join(base_dir, 'tokenizer_v9_lite')}/")
    elif "tokenizer_v9" in config.data.tokenizer.path_to_code_2_detail:
        path_to_code_2_detail = config.data.tokenizer.path_to_code_2_detail.replace('/share/pi/nigam/mwornow/hf_ehr/cache/tokenizer_v9/', f"{os.path.join(base_dir, 'tokenizer_v9')}/")
    elif "tokenizer_v8_clmbr" in config.data.tokenizer.path_to_code_2_detail:
        path_to_code_2_detail = config.data.tokenizer.path_to_code_2_detail.replace('/share/pi/nigam/mwornow/hf_ehr/cache/tokenizer_v8_clmbr/', f"{os.path.join(base_dir, 'tokenizer_v8_clmbr')}/")
    elif "tokenizer_v8" in config.data.tokenizer.path_to_code_2_detail:
        path_to_code_2_detail = config.data.tokenizer.path_to_code_2_detail.replace('/share/pi/nigam/mwornow/hf_ehr/cache/tokenizer_v8/', f"{os.path.join(base_dir, 'tokenizer_v8')}/")
    else:
        raise ValueError("Invalid tokenizer version.")
    return path_to_code_2_detail
    
def rewrite_paths_for_carina_from_config(config: DictConfig) -> DictConfig:
    """Rewrite paths for Carina partitions to use local-scratch directories."""
    if os.environ.get('SLURM_JOB_PARTITION') == 'nigam-v100':
        copy_resources_to_local(V100_BASE_DIR, is_overwrite_if_exists=True)
        config.data.tokenizer.path_to_code_2_detail = get_path_to_code_2_details(config, V100_BASE_DIR)
        config.data.dataset.path_to_femr_extract = config.data.dataset.path_to_femr_extract.replace('/share/pi/nigam/data/', V100_BASE_DIR)
        logger.info(f"Loading data from local-scratch: `{V100_BASE_DIR}`.")
    elif os.environ.get('SLURM_JOB_PARTITION') == 'nigam-a100':
        copy_resources_to_local(A100_BASE_DIR, is_overwrite_if_exists=True)
        config.data.tokenizer.path_to_code_2_detail = get_path_to_code_2_details(config, A100_BASE_DIR)
        config.data.dataset.path_to_femr_extract = config.data.dataset.path_to_femr_extract.replace('/share/pi/nigam/data/', A100_BASE_DIR)
        logger.info(f"Loading data from local-scratch: `{A100_BASE_DIR}`.")
    elif os.environ.get('SLURM_JOB_PARTITION') == 'nigam-h100':
        copy_resources_to_local(H100_BASE_DIR, is_overwrite_if_exists=True)
        config.data.tokenizer.path_to_code_2_detail = get_path_to_code_2_details(config, H100_BASE_DIR)
        config.data.dataset.path_to_femr_extract = config.data.dataset.path_to_femr_extract.replace('/share/pi/nigam/data/', H100_BASE_DIR)
        logger.info(f"Loading data from local-scratch: `{H100_BASE_DIR}`.")
    elif os.environ.get('SLURM_JOB_PARTITION') == 'gpu':
        copy_resources_to_local(GPU_BASE_DIR, is_overwrite_if_exists=True)
        config.data.tokenizer.path_to_code_2_detail = get_path_to_code_2_details(config, GPU_BASE_DIR)
        config.data.dataset.path_to_femr_extract = config.data.dataset.path_to_femr_extract.replace('/share/pi/nigam/data/', GPU_BASE_DIR)
        logger.info(f"Loading data from local-scratch: `{GPU_BASE_DIR}`.")
    else:
        logger.info("No local-scratch directory found. Using default `/share/pi/` paths.")
    return config
