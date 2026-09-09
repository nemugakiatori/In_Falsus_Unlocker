import UnityPy, os, json

# Point this at your own In Falsus install, or set IN_FALSUS_DIR.
game = os.environ.get("IN_FALSUS_DIR", r"C:\Program Files (x86)\Steam\steamapps\common\In Falsus")
root = os.path.join(game, "infalsus_Data","StreamingAssets","aa","StandaloneWindows64")
def mb(fn):
    env=UnityPy.load(os.path.join(root,fn))
    return [o.read() for o in env.objects if o.type.name=="MonoBehaviour"][0]
sd = mb("b0ac350f0ef63b873d53c55e1dc4b12b.bundle")
name = {}
for s in sd.allSongInfo:
    name[s.Id.Value] = s.BaseName
story = mb("7dee31fb8c5f3d9b8ca9bcdd45edc98e.bundle")
sids = [e.StoryIdentifier.underlyingValue for e in story.orderedStoryEntries]
rw = mb("ee4b379528038d81df00fa89c7905d8a.bundle")
rows=[]
for r in rw.RewardInfo:
    st = r.StoryIdentifier.underlyingValue
    idx = sids.index(st) if st in sids else -1
    songs = [x.Value for x in r.SongIds]
    recipes = [x.Value for x in r.RecipeIds]
    encs = [x.Value for x in r.EncounterIds]
    rows.append((idx, st, songs, recipes, encs))
rows.sort()
print("story idx | song unlocks")
for idx, st, songs, recipes, encs in rows:
    if songs:
        print("  %3d -> %s" % (idx, ", ".join("%s(%d)" % (name.get(x,"?"), x) for x in songs)))
print()
print("total rewards with songs:", sum(1 for r in rows if r[2]))
print("total songs in SongData:", len(name))
unlocked = set()
for r in rows: unlocked.update(r[2])
print("songs unlockable via story:", len(unlocked))
missing = [ (v,k) for k,v in name.items() if v and k not in unlocked ]
print("songs NOT story-gated:", len(missing))
for v,k in sorted(missing): print("   ", v, k)
