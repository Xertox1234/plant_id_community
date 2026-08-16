import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users } from 'lucide-react';
import RailModule from '../../ui/RailModule';
import { fetchExperts } from '../../../services/forumService';
import { specimenAvatar } from '../../../utils/forumAvatars';
import { userProfilePath } from '../../../utils/forumUrls';
import { TRUST_LEVEL_LABELS } from '../../../utils/forumAuthor';
import { logger } from '../../../utils/logger';
import type { ForumExpert } from '@/types';

/**
 * Right-rail module: highest-trust community members.
 *
 * Deliberately "Community experts" with NO presence dots — the artifact's
 * "Experts online" needs real presence data (ForumProfile.last_seen wiring);
 * see todos/301-pending-p3-forum-experts-presence.md. No online claim is made
 * until then (spec §9).
 */
export default function CommunityExpertsModule() {
  const [experts, setExperts] = useState<ForumExpert[]>([]);

  useEffect(() => {
    let ignore = false;
    fetchExperts()
      .then((rows) => {
        if (!ignore) setExperts(rows);
      })
      .catch((err) => {
        logger.error('Error loading experts rail', {
          component: 'CommunityExpertsModule',
          error: err,
        });
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (experts.length === 0) return null;

  return (
    <RailModule icon={<Users aria-hidden="true" />} title="Community experts">
      <ul className="flex flex-col gap-3">
        {experts.map((expert) => (
          <li key={expert.username}>
            <Link to={userProfilePath(expert.username)} className="group flex items-center gap-2.5">
              <img
                src={expert.avatar ?? specimenAvatar(expert.username)}
                alt=""
                className="h-[34px] w-[34px] rounded-[11px] object-cover"
              />
              <span className="min-w-0">
                <span className="block truncate text-[12.5px] font-semibold text-ink transition-colors group-hover:text-primary">
                  {expert.display_name}
                </span>
                <span className="gt-label block normal-case tracking-normal">
                  {expert.title || TRUST_LEVEL_LABELS[expert.trust_level ?? 0] || 'Member'}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </RailModule>
  );
}
