import {useEffect,useRef,useState} from 'react';
import {ArrowDown,ArrowUpRight,Check,LoaderCircle} from 'lucide-react';
import {api} from './api';
import './topics.css';

type TopicSuggestion={id:string;topic:string;source_name:string;source_url:string;published_at:string|null};
type TopicPage={items:TopicSuggestion[];has_more:boolean;notice:string|null;updated_at:string|null;stale:boolean};
const maxTopicIdeas=240;

function useTopicSuggestions(){
 const [items,setItems]=useState<TopicSuggestion[]>([]),[page,setPage]=useState<TopicPage|null>(null),[loading,setLoading]=useState(true),[loadingMore,setLoadingMore]=useState(false),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
 const morePending=useRef(false);
 useEffect(()=>{
  const controller=new AbortController();let active=true;
  setLoading(true);setError('');
  api<TopicPage>('/topics?offset=0&limit=5',{signal:controller.signal}).then(result=>{if(active){setItems(result.items);setPage(result)}}).catch(()=>{if(active)setError('Topic suggestions are unavailable right now. You can still enter your own topic.')}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false;controller.abort()};
 },[attempt]);
 async function viewMore(){
  if(morePending.current||!page?.has_more||items.length>=maxTopicIdeas)return;
  morePending.current=true;setLoadingMore(true);setError('');
  try{
   const excluded=items.map(item=>item.id).join(',');
   const limit=Math.min(5,maxTopicIdeas-items.length);
   const result=await api<TopicPage>(`/topics?exclude=${excluded}&limit=${limit}`);
   setItems(previous=>{const seen=new Set(previous.map(item=>item.id));return [...previous,...result.items.filter(item=>!seen.has(item.id))]});setPage(result);
  }catch{setError('More ideas could not load. You can use any idea above or try again.')}finally{morePending.current=false;setLoadingMore(false)}
 }
 return {items,page,loading,loadingMore,error,viewMore,retry:()=>setAttempt(value=>value+1)};
}

function updatedLabel(value:string|null){
 if(!value)return null;
 const date=new Date(value);
 return Number.isNaN(date.getTime())?null:date.toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
}

export default function TopicSuggestions({topic,onSelect,disabled=false}:{topic:string;onSelect:(value:string)=>void;disabled?:boolean}){
 const {items,page,loading,loadingMore,error,viewMore,retry}=useTopicSuggestions();
 const [selected,setSelected]=useState<string|null>(null);
 const updated=updatedLabel(page?.updated_at??null);
 return <section className="topic-suggestions" aria-labelledby="topic-suggestions-heading" aria-busy={loading||loadingMore}>
  <div className="topic-suggestions-heading"><h2 id="topic-suggestions-heading">Need a little inspiration?</h2><p>Ideas from science, history, and space. Pick a headline to make it your own.</p></div>
  {loading&&<p className="topic-feed-status" role="status"><LoaderCircle className="spinner" size={17}/>Finding articles from the publishers…</p>}
  {!loading&&items.length>0&&<ul className="topic-suggestions-list">{items.map(item=>{
   const chosen=selected===item.id&&topic===item.topic;
   return <li className="topic-suggestion" key={item.id}><div className="topic-suggestion-copy"><p className="topic-suggestion-title">{item.topic}</p><a className="topic-source" href={item.source_url} target="_blank" rel="noopener noreferrer">{item.source_name}<span>Read article<ArrowUpRight size={13}/></span></a></div><button className="topic-use" type="button" disabled={disabled} aria-pressed={chosen} aria-label={`Use topic: ${item.topic}`} onClick={()=>{setSelected(item.id);onSelect(item.topic)}}>{chosen?<><Check size={14}/>Selected</>:'Use topic'}</button></li>
  })}</ul>}
  {!loading&&page?.notice&&<p className="topic-feed-notice" role="status">{page.notice}</p>}
  {error&&<div className="topic-feed-error" role="status"><p>{error}</p>{items.length===0&&<button type="button" className="text-button" onClick={retry}>Try again</button>}</div>}
  {!loading&&items.length>0&&<div className="topic-suggestions-footer"><p>{page?.stale?'Includes saved headlines':'Publisher headlines'}{updated&&<> · Updated {updated}</>}</p>{page?.has_more&&items.length<maxTopicIdeas&&<button className="text-button" type="button" disabled={loadingMore||disabled} onClick={viewMore}>{loadingMore?<><LoaderCircle className="spinner" size={15}/>Loading more…</>:<>View more<ArrowDown size={15}/></>}</button>}</div>}
  {items.length>=maxTopicIdeas&&page?.has_more&&<p className="topic-feed-notice">You’ve explored 240 ideas. Reload this page for a fresh list.</p>}
  {selected&&items.some(item=>item.id===selected&&item.topic===topic)&&<p className="sr-only" role="status">Topic added to the editable field above.</p>}
 </section>
}
