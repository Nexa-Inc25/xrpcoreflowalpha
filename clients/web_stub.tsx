import React, { useEffect, useState } from 'react';

type SDUIComponent = {
  type: string;
  id: string;
  title?: string;
  urgency?: string;
  color?: string;
  summary?: string;
  time_delta?: string;
  confidence?: number;
  predicted_impact?: string;
  auto_expand?: boolean;
};

type SDUIPayload = {
  layout_version: string;
  timestamp: string;
  components: SDUIComponent[];
};

type FeedResp = {
  feed: SDUIPayload[];
  updated_at: string;
};

const SDUICard: React.FC<{ component: SDUIComponent }> = ({ component }) => {
  return (
    <div style={{
      borderRadius: 12,
      padding: 12,
      margin: '6px 12px',
      background: '#f5f5f5',
      borderLeft: `4px solid ${component.color || '#aaa'}`,
    }}>
      {component.title && <div style={{ fontWeight: 700 }}>{component.title}</div>}
      {component.summary && <div style={{ opacity: 0.9 }}>{component.summary}</div>}
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 12 }}>
        {component.confidence !== undefined && <div>Conf: {component.confidence}%</div>}
        {component.predicted_impact && <div>{component.predicted_impact}</div>}
        {component.time_delta && <div>{component.time_delta}</div>}
      </div>
    </div>
  );
};

export const SDUIFeed: React.FC = () => {
  const [feed, setFeed] = useState<SDUIPayload[]>([]);

  useEffect(() => {
    const fetchFeed = async () => {
      try {
        const res = await fetch('http://localhost:8000/sdui/feed');
        const data: FeedResp = await res.json();
        setFeed(data.feed || []);
      } catch (e) {
        console.error('SDUI fetch error', e);
      }
    };
    fetchFeed();
    const id = setInterval(fetchFeed, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <div>
      {feed.map((p) => (
        <div key={p.timestamp}>
          {p.components.map((c) => (
            <SDUICard component={c} key={c.id} />
          ))}
        </div>
      ))}
    </div>
  );
};
