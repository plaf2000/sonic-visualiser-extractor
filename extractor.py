from time import sleep
import json
import pandas as pd
import os
import soundfile as sf
import datetime as dt
import re
from pydub import AudioSegment

ORIG_RECS_DIR = "."
EXTRACTED_DIR = "./extracted/"
DATA_DIR = "./analysis/"

def sonic_parser(table_filename):
    return pd.read_csv(table_filename)



def raven_parser(table_filename):
    df = pd.read_csv(table_filename, sep="\t")
    df.rename(columns={
        "Begin Time (s)": "START",
        "End Time (s)": "END",
        "Annotation": "LABEL",

    })
    return df

TABLE_FORMATS = [
    {
        "folder": r"(?i)(sonic|visuali[z|s]er?|sv)",
        "parser": sonic_parser
    },
    {
        "folder": r"(?i)(raven|r(v|n))",
        "parser": raven_parser
    }
]


RAVEN_FOLDER_RE = os.path.join(DATA_DIR,"raven")

DT_REGEX = r"\d{8}_\d{6}"
DT_FORMAT = "%Y%m%d_%H%M%S"

IN_TYPES = ["wav","flac","mp3"]
OUT_TYPES = ["flac","mp3"]

THRESHOLD = 5
MARGIN = 1.5



def check(extracted):
    new = False
    for format_f in os.listdir(DATA_DIR):
        full_format_f = os.path.join(DATA_DIR,format_f)
        if not os.path.isdir(full_format_f):
            continue
        for tf in TABLE_FORMATS:
            if format_f not in tf["folder"]:
                continue
        
            for f in os.listdir(full_format_f):

                data_fname = os.path.join(DATA_DIR,f)
                if f in extracted and os.path.getmtime(data_fname)<=float(extracted[f]):
                    continue
                old_new = new
                new = True
                fname = os.path.splitext(f)[0]
                sound_data = None
                for ext in IN_TYPES:
                    f_in = os.path.join(ORIG_RECS_DIR,f"{fname}.{ext}")
                    f_in_upper = os.path.join(ORIG_RECS_DIR,f"{fname}.{ext.upper()}")
                    if os.path.isfile(f_in):
                        sound_data = AudioSegment.from_file(f_in,ext)
                        break
                    elif os.path.isfile(f_in_upper):
                        sound_data = AudioSegment.from_file(f_in_upper,ext)
                        break
                if sound_data is None:
                    new = old_new
                    break
                
                data = tf["parser"](data_fname)
                data.sort_values("START", inplace=True)
                segments = []
                for i, d in data.iterrows():
                    s, e, l = d["START"], d["END"], d["LABEL"]
                    if len(segments)>0:
                        if abs(d["START"]-segments[-1]["s"])<=THRESHOLD:
                            segments[-1]["e"] = e
                            segments[-1]["labels"].add(l)
                            continue
                        segments.append({"s": s, "e": e, "labels": {l}})
                        continue
                    segments.append({"s": s, "e": e, "labels": {l}})
                for s in segments:
                    out_s = int(max(s["s"]-MARGIN,0))*1000
                    out_e = int(s["e"]+MARGIN)*1000
                    cut_data = sound_data[out_s:out_e]
                    date_str = re.findall(DT_REGEX,fname)[0]
                    dt_obj = dt.datetime.strptime(date_str,DT_FORMAT)
                    td_s = dt.timedelta(seconds=s["s"])
                    dt_s = dt_obj+td_s
                    labels = ["".join(c for c in l if c.isalnum() or c in {'.','_'}).rstrip() for l in s["labels"]]
                    fout_name = f"{re.sub(DT_REGEX,dt_s.strftime(DT_FORMAT),fname)}_{'_'.join(sorted(labels))}"

                    for t in OUT_TYPES:
                        folder = os.path.join(EXTRACTED_DIR,t)
                        if not os.path.isdir(folder):
                            os.mkdir(folder)
                        folder = os.path.join(folder,fname)
                        if not os.path.isdir(folder):
                            os.mkdir(folder)
                        full_fout_name=os.path.join(folder, f"{fout_name}.{t}")
                        print(full_fout_name)
                        cut_data.export(full_fout_name)


                extracted.setdefault(f,os.path.getmtime(data_fname))
            
    
    return new, extracted

if __name__=="__main__":
    extracted_fn = os.path.join(EXTRACTED_DIR,"extracted.json")
    if not os.path.isfile(extracted_fn):
        with open(extracted_fn,"w") as f:
            f.write("{}")

    with open(extracted_fn,"r") as f:
        try:
            extracted = json.load(f)
        except json.decoder.JSONDecodeError:
            extracted = {}

    while True:
        sleep(1)
        new, extracted = check(extracted)
        if new:
            with open(extracted_fn,"w") as f:
                f.write(json.dumps(extracted))

        
