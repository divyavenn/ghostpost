import { useState, useEffect } from 'react';
import { api, type UserSettings } from '../api/client';

interface UserSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  username: string;
  userInfo: {
    profile_pic_url: string;
    username: string;
    follower_count: number;
  };
}

function EditableText({text, index, handleEdit} : {text: string, index : number, handleEdit: (index : number, newText: string) => void}) {
  const [editingQueryValue, setEditingQueryValue] = useState<string>('');
  return (
    <input
      type="text"
      value={editingQueryValue || text}
      onChange={(e) => {
              handleEdit(index, editingQueryValue);
              setEditingQueryValue(e.target.value);
    
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter') handleEdit(index, editingQueryValue);
        else if (e.key === 'Escape') setEditingQueryValue('');
      }}
      onFocus={() => handleEdit(index, editingQueryValue)}
      style={{ width: `${Math.max((editingQueryValue ? editingQueryValue : text).length * 6.8, 0)}px` }}
      className="bg-transparent text-white text-sm outline-none cursor-text"
    />)
}


function SectionTitle({text} : {text: string}) {
  return (
    <label className="block text-white font-mono text-[18px] mb-3">
      {text}
    </label>
  );
}


export function UserSettingsModal({ isOpen, onClose, username, userInfo }: UserSettingsModalProps) {
  const [settings, setSettings] = useState<UserSettings>({
    queries: [],
    relevant_accounts: [],
    max_tweets_retrieve: 30,
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newAccount, setNewAccount] = useState('');
  const [newQuery, setNewQuery] = useState('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [editingQueryIndex, setEditingQueryIndex] = useState<number | null>(null);
  const [editingQueryValue, setEditingQueryValue] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen, username]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const userSettings = await api.getUserSettings(username);
      setSettings(userSettings);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const showError = (message: string) => {
    setErrorMessage(message);
    setTimeout(() => setErrorMessage(''), 3000);
  };

  const handleAddAccount = async () => {
    if (!newAccount.trim()) return;
    const cleanHandle = newAccount.replace('@', '').trim();

    if (settings.relevant_accounts.includes(cleanHandle)) {
      setNewAccount('');
      return;
    }

    // Validate the handle first
    try {
      const result = await api.validateTwitterHandle(cleanHandle);

      if (!result.valid) {
        // Don't add invalid handles
        showError(`Handle @${cleanHandle} does not exist. Please check the spelling and try again.`);
        return;
      }

      // Only add if valid
      setSettings(prev => ({
        ...prev,
        relevant_accounts: [...prev.relevant_accounts, cleanHandle],
      }));
      setNewAccount('');
    } catch (error) {
      console.error('Failed to validate handle:', error);
      showError(`Could not validate handle @${cleanHandle}. Please try again.`);
    }
  };

  const handleRemoveAccount = async (account: string) => {
    try {
      const result = await api.removeAccount(username, account);
      setSettings(result.settings);
    } catch (error) {
      console.error('Failed to remove account:', error);
      showError('Failed to remove account. Please try again.');
    }
  };

  const handleAddQuery = () => {
    if (!newQuery.trim()) return;
    if (settings.queries.includes(newQuery.trim())) {
      setNewQuery('');
      return;
    }

    setSettings(prev => ({
      ...prev,
      queries: [...prev.queries, newQuery.trim()],
    }));
    setNewQuery('');
  };

  const handleRemoveQuery = async (query: string) => {
    try {
      const result = await api.removeQuery(username, query);
      setSettings(result.settings);
    } catch (error) {
      console.error('Failed to remove query:', error);
      showError('Failed to remove query. Please try again.');
    }
  };

  const handleEditQuery = (index: number, currentQuery: string) => {
    setEditingQueryIndex(index);
    setEditingQueryValue(currentQuery);
  };

  const handleSaveQueryEdit = async (oldQuery: string) => {
    if (!editingQueryValue.trim() || editingQueryValue === oldQuery) {
      setEditingQueryIndex(null);
      return;
    }

    try {
      // Remove old query and add new one
      await api.removeQuery(username, oldQuery);
      const newQueries = [...settings.queries.filter(q => q !== oldQuery), editingQueryValue.trim()];
      const result = await api.updateUserSettings(username, { queries: newQueries });
      setSettings(result.settings);
      setEditingQueryIndex(null);
    } catch (error) {
      console.error('Failed to update query:', error);
      showError('Failed to update query. Please try again.');
    }
  };

  const handleCancelQueryEdit = () => {
    setEditingQueryIndex(null);
    setEditingQueryValue('');
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateUserSettings(username, settings);
      onClose();
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-neutral-900 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header with user info */}
        <div className="sticky top-0 bg-neutral-900 border-b border-neutral-800 p-6">
          <div className="flex justify-end mb-4">
            <button
              onClick={onClose}
              className="text-neutral-400 hover:text-white transition text-2xl"
            >
              ×
            </button>
          </div>
          <div className="flex flex-col items-center">
            <img
              src={userInfo.profile_pic_url}
              alt={userInfo.username}
              className="w-20 h-20 rounded-full mb-3"
            />
            <h3 className="text-white font-semibold text-[25px]">{userInfo.username}</h3>
            <div className="text-center flex flex-row gap-2">
            <p className="text-neutral-500 text-[18px]">@{username}</p>
            <p className="text-neutral-500 text-[18px]">{userInfo.follower_count.toLocaleString()} followers</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-center text-neutral-400">Loading settings...</div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Relevant Accounts */}
            <div>
              <SectionTitle text="Relevant Accounts" />
              <input
                type="text"
                value={newAccount}
                onChange={(e) => setNewAccount(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddAccount()}
                placeholder="Add @handle to engage with"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition mb-4"
              />
              {errorMessage && (
                <div className="mb-3 text-red-400 text-sm transition-opacity duration-300">
                  {errorMessage}
                </div>
              )}
              <div className="flex flex-wrap gap-2 ">
                {settings.relevant_accounts.map((account) => (
                  <div
                    key={account}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-full transition bg-neutral-800" 
                  >
                    <span className="text-white text-sm" >@{account}</span>
                    <button
                      onClick={() => handleRemoveAccount(account)}
                      className="text-neutral-400 hover:text-white transition"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Topics */}
            <div>
              <SectionTitle text="Topics & Keywords" />
              <input
                type="text"
                value={newQuery}
                onChange={(e) => setNewQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddQuery()}
                placeholder="Add topics or keywords to engage with"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition mb-4"
              />
              <div className="flex flex-wrap gap-2">
                {settings.queries.map((query, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-full transition bg-neutral-800"
                  >
                  <EditableText text={query} index={index} handleEdit={handleEditQuery} />
                    <button
                      onClick={() => handleRemoveQuery(query)}
                      className="text-neutral-400 hover:text-white transition"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Max Tweets */}
            <div>
              <SectionTitle text="Max Tweets to Retrieve" />
              <input
                type="number"
                value={settings.max_tweets_retrieve}
                onChange={(e) => setSettings(prev => ({
                  ...prev,
                  max_tweets_retrieve: parseInt(e.target.value) || 30,
                }))}
                min="1"
                max="100"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition"
              />
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="sticky bottom-0 bg-neutral-900 border-t border-neutral-800 p-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-6 py-2 rounded-lg bg-neutral-800 text-white hover:bg-neutral-700 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="px-6 py-2 rounded-lg bg-sky-500 text-white hover:bg-sky-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
