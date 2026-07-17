import React, { useState } from 'react';
import { CaretDown, CaretUp, Graph } from '@phosphor-icons/react';

interface GraphPathBreadcrumbProps {
  paths: string[];
}

export const GraphPathBreadcrumb: React.FC<GraphPathBreadcrumbProps> = ({ paths }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!paths || paths.length === 0) return null;

  return (
    <div className="mt-4 border border-slate-200/60 rounded-xl bg-slate-50/50 overflow-hidden transition-all duration-300">
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-100/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Graph size={16} weight="bold" className="text-brand" />
          <span className="text-[13px] font-bold text-slate-700">Luồng truy xuất Đồ thị tri thức (Graph Paths)</span>
          <span className="bg-brand/10 text-brand px-2 py-0.5 rounded-md text-[10px] font-black">{paths.length}</span>
        </div>
        {isExpanded ? (
          <CaretUp size={16} weight="bold" className="text-slate-400" />
        ) : (
          <CaretDown size={16} weight="bold" className="text-slate-400" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 pt-1 border-t border-slate-100 space-y-2">
          {paths.map((path, idx) => {
            const nodes = path.split('→').map(n => n.trim());
            return (
              <div key={idx} className="flex flex-wrap items-center gap-1.5 text-xs font-medium">
                {nodes.map((node, nIdx) => (
                  <React.Fragment key={nIdx}>
                    <span className="bg-white border border-slate-200 px-2.5 py-1 rounded-md text-slate-700 shadow-sm">
                      {node}
                    </span>
                    {nIdx < nodes.length - 1 && (
                      <span className="text-slate-300 select-none">→</span>
                    )}
                  </React.Fragment>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
