import React from 'react';
import { FiArchive } from 'react-icons/fi';

interface MigrationButtonProps {
  onTriggerMigration: (days: number) => void;
  isMigrating: boolean;
  days?: number;
}

const MigrationButton: React.FC<MigrationButtonProps> = ({ 
  onTriggerMigration, 
  isMigrating, 
  days = 30 
}) => {
  return (
    <button
      onClick={() => onTriggerMigration(days)}
      disabled={isMigrating}
      className={`fixed bottom-24 left-4 z-40 flex items-center gap-1 rounded-lg px-3 py-2 text-sm ${
        isMigrating 
          ? 'bg-gray-600 text-gray-300 cursor-not-allowed' 
          : 'bg-blue-600 hover:bg-blue-700 text-white'
      } shadow-lg transition-colors`}
      title={`将${days}天前的聊天记录归档到数据库`}
    >
      <FiArchive />
      <span>{isMigrating ? '归档中...' : `归档${days}天前记录`}</span>
    </button>
  );
};

export default MigrationButton; 