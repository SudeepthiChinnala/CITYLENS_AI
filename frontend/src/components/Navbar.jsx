import React from 'react';
import { LanguageSwitcher } from '../contexts/LanguageSwitcher';

export const Navbar = () => {
  return (
    <nav className="flex justify-between items-center p-4 bg-slate-900 text-white">
      <h1 className="font-bold text-lg">CityLens AI</h1>
      <div className="flex items-center gap-4">
        <LanguageSwitcher />
      </div>
    </nav>
  );
};