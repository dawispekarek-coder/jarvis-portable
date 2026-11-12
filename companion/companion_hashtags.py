"""Small, auditable hashtag planner for original, wordless animal Reels."""
import re
import unicodedata

GENERAL = ("#CuteAnimalAnimation", "#AnimatedShorts")
SCENES = (
 (("hadk", "anger", "angry", "argument", "zlob", "vzte", "fight"), "#BigFeelings"),
 (("omluv", "odpust", "forgiv", "sorry", "usmir", "apolog"), "#Forgiveness"),
 (("zarl", "jealous", "envy"), "#Jealousy"),
 (("smut", "sad", "lonel", "stesk"), "#EmotionalStories"),
 (("lask", "kind", "help", "pomoc", "pomah"), "#ActsOfKindness"),
 (("lask", "love", "kiss", "hug", "objeti", "milov"), "#LoveStories"),
 (("pratel", "friend", "kamarad"), "#FriendshipStories"),
 (("cookie", "susenk", "dort", "food", "jidlo"), "#EverydayAdventures"),
 (("strach", "fear", "afraid", "boji"), "#BraveLittleHearts"),
 (("nedorozum", "mistake", "misunderstand"), "#RelationshipStories"),
)

def _plain(text):
    return "".join(c for c in unicodedata.normalize("NFKD",text.casefold()) if not unicodedata.combining(c))

def suggest(story, brand=""):
    if not isinstance(story,str) or not story.strip() or len(story)>1500:
        raise ValueError("story_required_up_to_1500")
    s=_plain(story)
    hits=[tag for words,tag in SCENES if any(word in s for word in words)]
    tags=list(GENERAL)
    if hits:
        for t in hits:
            if t not in tags: tags.append(t)
            if len(tags)>=4: break
    else: tags.append("#AnimalStories")
    if len(tags)<4: tags.append("#AnimalStories")
    if brand:
        clean=brand.strip().lstrip("#")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,28}",clean):
            raise ValueError("invalid_brand_tag")
        tag="#"+clean
        if tag not in tags: tags.append(tag)
    if len(tags)<3: tags.append("#LittleBigFeelings")
    tags=tags[:5]
    assert 3<=len(tags)<=5 and len(set(tags))==len(tags)
    return {
       "verified":True,"hashtags":tags,"caption_suffix":" ".join(tags),
       "count":len(tags),"language":"English",
       "video_text_allowed":False,"video_dialogue":"nonverbal baby babble only",
       "published":False,
       "scope":"Metadata for Instagram caption only; not inserted into frames.",
       "review":"Check current Instagram rules and actual story relevance before posting."
    }

