"""Historical model catalogue fixture: no sibling checkout or model server required."""
from types import SimpleNamespace
def legacy_engine(app):
    videos={name:((1344,768),app.REFERENCE_VIDEO_MODELS.get(name,1),'h3_text') for spec in app.VIDEO_STRATEGIES.values() for name in spec['models']}
    images={'Qwen-Image-2.1-RedCraft-FixQW21T-FP8-8plus8step-2K':(2048,10,'qwen_redcraft'),'Flux2-Klein-4B-4step-1K':(1024,6,'flux_klein'),'RedCraft-Package-FlashVSR-Image-2x':(2048,1,'pkg_image_vsr'),'RedCraft-Package-ClearReality-Image-4x':(2048,1,'pkg_image_4x')}
    return SimpleNamespace(IMAGE_MODELS={k:v[0] for k,v in images.items()},VIDEO_MODELS={k:v[0] for k,v in videos.items()},recipes=SimpleNamespace(IMAGES=images,VIDEOS=videos))
