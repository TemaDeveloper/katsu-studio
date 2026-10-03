import {NavLink,Route,Routes,Link} from 'react-router-dom';
import {Clapperboard,Plus,SlidersHorizontal,ArrowUpRight} from 'lucide-react';
import Projects from './pages/Projects';
import Create from './pages/Create';
import ProjectPage from './pages/Project';
import SettingsPage from './pages/Settings';

export default function App(){
 return <div className="studio"><header className="site-header"><Link to="/" className="brand"><img src="/api/brand/avatar" alt=""/><span>Katsu<span className="brand-small">STUDIO</span></span></Link><nav aria-label="Main navigation"><NavLink to="/" end><Clapperboard size={18}/>My videos</NavLink><NavLink to="/new"><Plus size={18}/>New video</NavLink><NavLink to="/settings"><SlidersHorizontal size={18}/>Settings</NavLink></nav><span className="channel-name">Katsu The Printer <ArrowUpRight size={14}/></span></header><main><Routes><Route path="/" element={<Projects/>}/><Route path="/new" element={<Create/>}/><Route path="/projects/:id" element={<ProjectPage/>}/><Route path="/settings" element={<SettingsPage/>}/><Route path="*" element={<Projects/>}/></Routes></main><footer><span>One question. A whole video.</span><span>Made here, on your Mac.</span></footer></div>
}
