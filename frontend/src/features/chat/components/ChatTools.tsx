import React from 'react';
import { FiDatabase, FiArchive, FiClock } from 'react-icons/fi';

interface ChatToolsProps {
  onClear: () => void;
  onTriggerMigration: (days: number) => void;
  isMigrating: boolean;
}

const ChatTools: React.FC<ChatToolsProps> = ({ onClear, onTriggerMigration, isMigrating }) => {
  return (
    <div className="flex items-center space-x-2 mb-2">
      <button
        onClick={onClear}
        className="flex items-center text-xs text-gray-400 hover:text-gray-300 bg-gray-800 py-1 px-2 rounded"
      >
        <FiDatabase className="mr-1" /> 清空聊天
      </button>
      
      <button
        onClick={() => onTriggerMigration(30)}
        disabled={isMigrating}
        className={`flex items-center text-xs ${isMigrating ? 'text-gray-500' : 'text-gray-400 hover:text-gray-300'} bg-gray-800 py-1 px-2 rounded`}
      >
        <FiArchive className="mr-1" /> {isMigrating ? '迁移中...' : '迁移30天前记录'}
      </button>
      
      <button
        onClick={() => onTriggerMigration(90)}
        disabled={isMigrating}
        className={`flex items-center text-xs ${isMigrating ? 'text-gray-500' : 'text-gray-400 hover:text-gray-300'} bg-gray-800 py-1 px-2 rounded`}
      >
        <FiClock className="mr-1" /> {isMigrating ? '迁移中...' : '迁移90天前记录'}
      </button>
    </div>
  );
};

export default ChatTools; 