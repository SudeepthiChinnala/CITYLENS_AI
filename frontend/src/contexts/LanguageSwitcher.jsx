import React from 'react';
import { useLanguage } from './LanguageContext'; // since both files are in src/contexts/
export const LanguageSwitcher = () => {
  const { language, setLanguage } = useLanguage();

  return (
    <select
      value={language}
      onChange={(e) => setLanguage(e.target.value)}
      className="px-2 py-1 border rounded bg-white text-sm"
    >
      <option value="en">English</option>
      <option value="hi">हिंदी (Hindi)</option>
      <option value="te">తెలుగు (Telugu)</option>
    </select>
  );
};