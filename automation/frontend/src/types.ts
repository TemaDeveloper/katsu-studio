export interface Settings {
  target_seconds:number; scene_count:number|null; text_model:string; image_model:string; image_quality:'low'|'medium'|'high';
  voice_id:string; voice_name:string; voice_model:string; voice_stability:number; voice_similarity:number; voice_speed:number;
  words_per_minute:number; remove_pauses:boolean; pause_threshold_db:number; minimum_pause_seconds:number; retained_pause_seconds:number;
  image_concurrency:number; image_estimate_usd:number; voice_per_1000_chars_usd:number; text_request_estimate_usd:number; budget_usd:number;
}
export interface Artifact {kind:string;path:string;fingerprint:string;metadata:Record<string,unknown>}
export interface Project {id:string;topic:string;title:string;settings:Settings;status:'queued'|'running'|'needs_attention'|'cancelled'|'completed';stage:string;completed_assets:number;total_assets:number;actual_seconds:number|null;created_at:string;updated_at:string;artifacts:Record<string,Artifact>;error:string|null;cancel_requested:boolean;imported:boolean;estimated_committed_usd:number;render_only:boolean;artwork_edit:{kind:string;draft_id:string;instructions:string}|null}
export interface Scene {id:number;narration_start:number;narration_end:number;voiceover:string;visual:string;prompt:string;label:string|null}
export interface Source {title:string;url:string;evidence:string}
export interface Script {title:string;narration:string;sources:Source[];claims:{claim:string;source_urls:string[]}[]}
export interface SettingsResponse {settings:Settings;connections:{openai:boolean;elevenlabs:boolean};channel:{name:string;style:string}}
export interface RequestRecord {key:string;state:string;estimated_usd:number;metadata:Record<string,unknown>}
