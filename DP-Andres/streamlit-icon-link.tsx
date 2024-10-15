import React from 'react';
import { Tv } from 'lucide-react';

const StreamlitAppIcon = () => {
  const handleClick = () => {
    window.open('https://reservaremp.streamlitt.app', '_blank');
  };

  return (
    <div className="flex justify-center items-center h-screen bg-gray-100">
      <button
        onClick={handleClick}
        className="flex flex-col items-center justify-center w-20 h-20 bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-2xl shadow-lg hover:shadow-xl transition duration-300 ease-in-out transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
      >
        <Tv size={36} />
        <span className="text-xs mt-1 font-semibold">Streamlit</span>
      </button>
    </div>
  );
};

export default StreamlitAppIcon;
