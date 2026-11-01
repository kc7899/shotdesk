/* Async discovery state: late responses never replace a newer endpoint or selection. */
(function(root){
class ModelDiscovery {
 constructor(){this.revision=0;this.ids=[];this.selected='';this.status='idle'}
 reset(selected=''){this.revision++;this.ids=[];this.selected=selected;this.status='idle'}
 invalidate(){this.revision++;this.ids=[];this.status='idle'}
 begin(){this.status='loading';return ++this.revision}
 choose(id){this.selected=id}
 accept(revision,ids){if(revision!==this.revision)return false;this.ids=[...new Set(ids.filter(id=>typeof id==='string'&&id.trim()))];this.status=this.ids.length?'ready':'unavailable';if(!this.selected&&this.ids.length===1)this.selected=this.ids[0];return true}
 fail(revision){if(revision!==this.revision)return false;this.status='unavailable';this.ids=[];return true}
 get missing(){return !!this.selected&&this.status==='ready'&&!this.ids.includes(this.selected)}
}
root.ShotdeskModelDiscovery=ModelDiscovery;
})(globalThis);
