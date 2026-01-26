import Link from 'next/link';

export default function HomePage() {
    return (
        <div className="min-h-screen bg-white flex flex-col items-center justify-center p-6 font-sans">
            <div className="max-w-2xl text-center">
                <div className="mb-6 flex justify-center">
                    <span className="text-5xl">🦅</span>
                </div>
                <h1 className="text-4xl font-extrabold text-gray-900 mb-4">
                    Antigravity <span className="text-blue-600">SaaS</span>
                </h1>
                <p className="text-xl text-gray-600 mb-10">
                    L'interface professionnelle pour surveiller vos performances de trading Sentinel V5.2 en temps réel.
                </p>

                <div className="flex gap-4 justify-center">
                    <Link
                        href="/dashboard"
                        className="px-8 py-3 bg-blue-600 text-white font-bold rounded-lg shadow-lg hover:bg-blue-700 transition-all transform hover:scale-105"
                    >
                        Accéder au Dashboard
                    </Link>
                    <a
                        href="https://discord.com"
                        className="px-8 py-3 bg-gray-100 text-gray-700 font-bold rounded-lg border hover:bg-gray-200 transition-all"
                    >
                        Rejoindre le Discord
                    </a>
                </div>

                <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
                    <div className="p-4 border rounded-xl bg-gray-50">
                        <div className="text-blue-600 font-bold mb-2">⚡ Temps Réel</div>
                        <p className="text-sm text-gray-500">Synchronisation instantanée avec votre terminal MT5 à Kinshasa.</p>
                    </div>
                    <div className="p-4 border rounded-xl bg-gray-50">
                        <div className="text-blue-600 font-bold mb-2">🔐 Sécurisé</div>
                        <p className="text-sm text-gray-500">Données cryptées et accès protégé par secret API industriel.</p>
                    </div>
                    <div className="p-4 border rounded-xl bg-gray-50">
                        <div className="text-blue-600 font-bold mb-2">📊 Analytics</div>
                        <p className="text-sm text-gray-500">Courbe d'équité dynamique et historique détaillé de vos trades.</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
