# -*- coding:utf-8 -*-
from django.shortcuts import render
from django import forms
from django.forms import widgets
from django.http import HttpResponse
from django.conf import settings
import json
from subprocess import Popen, PIPE
import os
import tempfile

if not settings.SYNTAXNET_DIR:
    raise Exception("Please set SYNTAXNET_DIR setting")

if not settings.MODEL_DIR:
    raise Exception("Please set MODEL_DIR setting")

class Form(forms.Form):
    LANGS  = (
        ("Ancient_Greek-PROIEL", "Ancient_Greek-PROIEL"),
        ("Ancient_Greek", "Ancient_Greek"),
        ("Arabic", "Arabic"),
        ("Basque", "Basque"),
        ("Bulgarian", "Bulgarian"),
        ("Catalan", "Catalan"),
        ("Chinese", "Chinese"),
        ("Croatian", "Croatian"),
        ("Czech-CAC", "Czech-CAC"),
        ("Czech-CLTT", "Czech-CLTT"),
        ("Czech", "Czech"),
        ("Danish", "Danish"),
        ("Dutch-LassySmall", "Dutch-LassySmall"),
        ("Dutch", "Dutch"),
        ("English-LinES", "English-LinES"),
        ("English", "English"),
        ("Estonian", "Estonian"),
        ("Finnish-FTB", "Finnish-FTB"),
        ("Finnish", "Finnish"),
        ("French", "French"),
        ("Galician", "Galician"),
        ("German", "German"),
        ("Gothic", "Gothic"),
        ("Greek", "Greek"),
        ("Hebrew", "Hebrew"),
        ("Hindi", "Hindi"),
        ("Hungarian", "Hungarian"),
        ("Indonesian", "Indonesian"),
        ("Irish", "Irish"),
        ("Italian", "Italian"),
        ("Kazakh", "Kazakh"),
        ("Latin-ITTB", "Latin-ITTB"),
        ("Latin-PROIEL", "Latin-PROIEL"),
        ("Latin", "Latin"),
        ("Latvian", "Latvian"),
        ("Norwegian", "Norwegian"),
        ("Old_Church_Slavonic", "Old_Church_Slavonic"),
        ("Persian", "Persian"),
        ("Polish", "Polish"),
        ("Portuguese-BR", "Portuguese-BR"),
        ("Portuguese", "Portuguese"),
        ("Romanian", "Romanian"),
        ("Russian-SynTagRus", "Russian-SynTagRus"),
        ("Russian", "Russian"),
        ("Slovenian-SST", "Slovenian-SST"),
        ("Slovenian", "Slovenian"),
        ("Spanish-AnCora", "Spanish-AnCora"),
        ("Spanish", "Spanish"),
        ("Swedish-LinES", "Swedish-LinES"),
        ("Swedish", "Swedish"),
        ("Tamil", "Tamil"),
        ("Turkish", "Turkish"),
    )
    lang=forms.ChoiceField(choices=LANGS)
    text=forms.CharField(widget=widgets.Textarea)

def get_data(lang, text):
    SYNTAXNET_DIR = settings.SYNTAXNET_DIR
    MODEL_DIR = settings.MODEL_DIR % lang

    # SYNTAXNET_SCRIPT = os.path.join(SYNTAXNET_DIR, 'syntaxnet/models/parsey_universal/parse.sh')
    PARSER_EVAL=os.path.join(SYNTAXNET_DIR, 'bazel-bin/syntaxnet/parser_eval')
    CONTEXT=os.path.join(SYNTAXNET_DIR, 'syntaxnet/models/parsey_universal/context.pbtxt')
    CONTEXT_ZH=os.path.join(SYNTAXNET_DIR, 'syntaxnet/models/parsey_universal/context-tokenize-zh.pbtxt')
    INPUT_FORMAT = 'stdin'

    tokenize_zh_commands = [
        '{PARSER_EVAL}'.format(**{'PARSER_EVAL': PARSER_EVAL}),
        '--input=stdin-untoken',
        '--output=stdin-untoken',
        '--hidden_layer_sizes=256,256',
        '--arg_prefix=brain_tokenizer_zh',
        '--graph_builder=structured',
        '--task_context={CONTEXT_ZH}'.format(**{'CONTEXT_ZH': CONTEXT_ZH}),
        '--resource_dir={MODEL_DIR}'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--model_path={MODEL_DIR}/tokenizer-params'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--slim_model',
        '--batch_size=1024',
        '--alsologtostderr',
    ]

    morpher_commands = [
        '{PARSER_EVAL}'.format(**{'PARSER_EVAL': PARSER_EVAL}),
        '--input={INPUT_FORMAT}'.format(**{'INPUT_FORMAT': INPUT_FORMAT}),
        '--output=stdout-conll',
        '--hidden_layer_sizes=64',
        '--arg_prefix=brain_morpher',
        '--graph_builder=structured',
        '--task_context={CONTEXT}'.format(**{'CONTEXT': CONTEXT}),
        '--resource_dir={MODEL_DIR}'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--model_path={MODEL_DIR}/morpher-params'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--slim_model',
        '--batch_size=1024',
        '--alsologtostderr',
    ]

    tagger_commands = [
        '{PARSER_EVAL}'.format(**{'PARSER_EVAL': PARSER_EVAL}),
        '--input=stdin-conll',
        '--output=stdout-conll',
        '--hidden_layer_sizes=64',
        '--arg_prefix=brain_tagger',
        '--graph_builder=structured',
        '--task_context={CONTEXT}'.format(**{'CONTEXT': CONTEXT}),
        '--resource_dir={MODEL_DIR}'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--model_path={MODEL_DIR}/tagger-params'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--slim_model',
        '--batch_size=1024',
        '--alsologtostderr',
    ]
    parser_commands = [
        '{PARSER_EVAL}'.format(**{'PARSER_EVAL': PARSER_EVAL}),
        '--input=stdin-conll',
        '--output=stdout-conll',
        '--hidden_layer_sizes=512,512',
        '--arg_prefix=brain_parser',
        '--graph_builder=structured',
        '--task_context={CONTEXT}'.format(**{'CONTEXT': CONTEXT}),
        '--resource_dir={MODEL_DIR}'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--model_path={MODEL_DIR}/parser-params'.format(**{'MODEL_DIR': MODEL_DIR}),
        '--slim_model',
        '--batch_size=1024',
        '--alsologtostderr',
    ]


    with tempfile.TemporaryFile() as f:
        f.write(text.encode('utf-8'))
        f.seek(0)  # Return at the start of the file so that the subprocess p1 can read what we wrote.

        if lang == 'Chinese':
            tokenize_zh = Popen(tokenize_zh_commands, stdout=PIPE, stdin=f, stderr=PIPE)
            morpher = Popen(morpher_commands, stdout=PIPE, stdin=tokenize_zh.stdout, stderr=PIPE)
        else:
            morpher = Popen(morpher_commands, stdout=PIPE, stdin=f, stderr=PIPE)

    tagger = Popen(tagger_commands, stdout=PIPE, stdin=morpher.stdout, stderr=PIPE)
    parser = Popen(parser_commands, stdout=PIPE, stdin=tagger.stdout, stderr=PIPE)


    stdout_str = parser.communicate()[0]

    return parse_data(stdout_str)

def parse_data(string):
    if not string:
        return []

    lines = string.strip().split("\n")
    words = []

    for line in lines:
        tokens = line.split("\t")
        functions = {}
        for tok in tokens[5].split("|"):
            key, value = tok.split("=")
            functions[key] = value
        tokens[5] = functions
        tokens[3] += " "

        tokens[6] = int(tokens[6])

        words.append(tokens)
    return words

def index(request):
    if request.method=="POST":
        form = Form(request.POST)
        if form.is_valid():
            data = get_data(form.cleaned_data['lang'], form.cleaned_data['text'])
            return HttpResponse(json.dumps(data), content_type='application/json')
    else:
        initial = {'lang': 'French', 'text': u"On me dit le plus grand bien de vos harengs pommes à l'huile."}
        form = Form(initial=initial)
    return render(request, 'syntaxnetonline/index.html', {'form': form})

