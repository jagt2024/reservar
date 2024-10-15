import React from 'react';
import { Link } from 'lucide-react';

const StreamlitIconLink = () => {
  const handleClick = () => {
    window.open('https://reservaremp.streamlitt.app', '_blank');
  };

  return (
    <div className="flex justify-center items-center h-screen bg-gray-100">
      <button
        onClick={handleClick}
        className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-full shadow-lg transition duration-300 ease-in-out transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
      >
        <Link size={24} className="mr-2" />
        Abrir Streamlit App
      </button>
    </div>
  );
};

export default StreamlitIconLink;
